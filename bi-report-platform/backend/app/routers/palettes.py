"""Saved chart colour palettes.

A palette is someone's own unless they share it; a manager can edit anyone's. The built-in
palettes are not rows here - they live in the frontend and never change - so "duplicate a
built-in one" arrives as an ordinary create with the colours already filled in.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ColorPalette, User
from ..schemas import PaletteIn, PaletteOut, PaletteUpdate

router = APIRouter(prefix="/api/palettes", tags=["palettes"])

MAX_PER_PERSON = 60  # a guard against a runaway "Duplicate" button, not a quota anyone will meet


def can_edit(p: ColorPalette, user: User) -> bool:
    return user.role == "manager" or p.owner_id == user.id


def to_out(p: ColorPalette, owner_name: str, user: User) -> PaletteOut:
    return PaletteOut(id=p.id, name=p.name, colors=list(p.colors or []), is_shared=p.is_shared,
                      owner_id=p.owner_id, owner_name=owner_name, can_edit=can_edit(p, user))


def visible(user: User):
    """A person sees their own palettes and the shared ones; a manager sees every one."""
    if user.role == "manager":
        return ColorPalette.id.is_not(None)
    return or_(ColorPalette.owner_id == user.id, ColorPalette.is_shared.is_(True))


def get_palette(db: Session, palette_id: int, user: User) -> ColorPalette:
    p = db.get(ColorPalette, palette_id)
    # A palette someone else keeps to themselves is reported as missing rather than as forbidden,
    # which would confirm it exists.
    if p is None or not (user.role == "manager" or p.owner_id == user.id or p.is_shared):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Palette not found")
    return p


def free_name(db: Session, name: str, owner_id: int | None, except_id: int | None = None) -> str:
    """A name this person isn't already using, with "(2)", "(3)"... added when they are. Duplicating
    a palette shouldn't fail over its name; it should just be called something slightly different."""
    taken = set(db.scalars(select(func.lower(ColorPalette.name))
                           .where(ColorPalette.owner_id == owner_id,
                                  ColorPalette.id != (except_id or -1))).all())
    if name.lower() not in taken:
        return name
    stem = name[:52]
    for n in range(2, 100):
        candidate = f"{stem} ({n})"
        if candidate.lower() not in taken:
            return candidate
    raise HTTPException(status.HTTP_409_CONFLICT, f'You already have many palettes called "{name}"')


@router.get("", response_model=list[PaletteOut])
def list_palettes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(ColorPalette, User.full_name)
                      .join(User, User.id == ColorPalette.owner_id, isouter=True)
                      .where(visible(user))
                      .order_by(func.lower(ColorPalette.name))).all()
    return [to_out(p, name or "", user) for p, name in rows]


@router.post("", response_model=PaletteOut, status_code=status.HTTP_201_CREATED)
def create_palette(body: PaletteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mine = db.scalar(select(func.count(ColorPalette.id)).where(ColorPalette.owner_id == user.id)) or 0
    if mine >= MAX_PER_PERSON:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"You already have {MAX_PER_PERSON} palettes. Delete one to save another.")
    if body.is_shared and user.role != "manager":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a manager can share a palette with everyone.")
    p = ColorPalette(name=free_name(db, body.name.strip(), user.id), colors=body.colors,
                     is_shared=body.is_shared, owner_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return to_out(p, user.full_name, user)


@router.put("/{palette_id}", response_model=PaletteOut)
def update_palette(palette_id: int, body: PaletteUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    p = get_palette(db, palette_id, user)
    if not can_edit(p, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This palette belongs to someone else.")
    if body.is_shared is not None and body.is_shared != p.is_shared and user.role != "manager":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a manager can share a palette with everyone.")
    if body.name is not None:
        p.name = free_name(db, body.name.strip(), p.owner_id, except_id=p.id)
    if body.colors is not None:
        p.colors = body.colors
    if body.is_shared is not None:
        p.is_shared = body.is_shared
    db.commit()
    db.refresh(p)
    owner = db.get(User, p.owner_id) if p.owner_id else None
    return to_out(p, owner.full_name if owner else "", user)


@router.post("/{palette_id}/duplicate", response_model=PaletteOut, status_code=status.HTTP_201_CREATED)
def duplicate_palette(palette_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A copy of a palette, owned by whoever asked. The copy is private even when the original was
    shared: sharing is a decision about the new palette, taken separately."""
    source = get_palette(db, palette_id, user)
    return create_palette(PaletteIn(name=f"{source.name} copy", colors=list(source.colors or []),
                                    is_shared=False), db, user)


@router.delete("/{palette_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_palette(palette_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Deletes a palette. Charts that used it keep their colours: a palette is copied into a chart
    when it is applied, so nothing on a saved report changes when the palette goes."""
    p = get_palette(db, palette_id, user)
    if not can_edit(p, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This palette belongs to someone else.")
    db.delete(p)
    db.commit()
