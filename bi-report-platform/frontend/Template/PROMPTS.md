# Prompts for the GRC report templates

Written for: anyone building these reports in the BI Report Platform.

Two of the reports in this folder now ship as built-in templates, under **Templates → GRC**:

| Report | Template | Folder |
| --- | --- | --- |
| `New report.pdf` — Audit Plan Item Overview | **OpenPages: Audit plan item overview** | GRC → IAM |
| `Action ITem.pdf` — Action Item Monitoring Dashboard | **OpenPages: Action item monitoring dashboard** | GRC → ORM |

Pick the template, choose the OpenPages connection, and the dashboard is built from ready-written
queries — no AI model is involved, so nothing is invented and nothing waits on the model.

The prompts below are for when you want the same shape of report built by the assistant instead:
a different object type, an extra breakdown, your own field names. Paste one into **Build a
dashboard**, choose the OpenPages connection, and edit the parts in *italics*.

---

## Audit Plan Item Overview

```
Build an Audit Plan Item Overview dashboard from the "Audit Plan Item" object type.

Show six breakdowns, each a count of plan items per value, largest first:
  - Status            (IAM-PlanItem-FG:Status)        as a pie chart
  - Type              (IAM-PlanItem-FG:Type)          as a pie chart
  - Risk Level        (IAM-PlanItem-FG:RskLvl)        as a bar chart
  - Priority          (IAM-PlanItem-FG:Prty)          as a bar chart
  - Planned Quarter   (IAM-PlanItem-FG:PlnQtr)        as a pie chart
  - Auditable Unit    (IAM-PlanItem-FG:AudUnt)        as a bar chart

Then a table of the plan items ordered by estimated effort, largest first, with:
name, description, status, estimated effort, planned quarter, priority, planned start date,
planned end date, type, risk level and creation date.

Do not add "IS NOT NULL" to the Audit Plan Item field groups: that object type refuses it.
Add filters for plan item status and risk level.
```

## Action Item Monitoring Dashboard

```
Build an Action Item Monitoring Dashboard from the ActionItem object type, tracking the status,
progress and ageing of management action items.

Three number tiles across the top: total action items, open action items
(OPSS-ActItem:Status = 'Open') and closed action items (OPSS-ActItem:Status = 'Closed').

Then three charts side by side:
  - Action items by status           (OPSS-ActItem:Status) as a pie chart
  - Action item ageing analysis      (OPSS-ActItem:Aging Bucket) as a bar chart
  - Action item submit for approval  (OPSS-ActItem:Submit for Approval) as a pie chart

Then a table of the action items with the highest open duration: every item that is not closed,
oldest start date first, with name, description, status, start date and due date.

Add filters for action item status and for the due date.
```

---

## Writing your own

Four things make the difference between a prompt that builds and one that half-builds:

1. **Name the object type exactly as OpenPages has it**, in the words of the connection's shared
   types — `Audit Plan Item` has spaces in it, `ActionItem` does not.
2. **Name the fields.** OpenPages field names carry their group (`OPSS-Ctl:Control Type`,
   `IAM-PlanItem-FG:Status`), and the group differs between installations. The Data Model page
   lists what each type really has on your connection.
3. **Say what each tile is** — a number, a pie, a bar, a table — and what it counts. OpenPages SQL
   can only count, so "total exposure" or "average effort" cannot be charted; put the amounts in a
   table instead.
4. **Keep it to one object type per counted chart.** OpenPages cannot count across a join. A list
   may join, by hierarchy: `FROM [SOXIssue] JOIN [ActionItem] ON PARENT([SOXIssue])`.

Enum fields are stored as codes in some installations (`1`, `2`, `3`) and shown as words
(`Planned`, `Scheduled`, `In Progress`). The charts and the filters both show the words.
