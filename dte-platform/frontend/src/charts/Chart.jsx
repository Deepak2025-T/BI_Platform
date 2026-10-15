import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

export default function Chart({ option, style }) {
  const el = useRef(null)
  const inst = useRef(null)
  useEffect(() => {
    inst.current = echarts.init(el.current, null, { renderer: 'canvas' })
    const ro = new ResizeObserver(() => inst.current && inst.current.resize())
    ro.observe(el.current)
    return () => { ro.disconnect(); inst.current.dispose(); inst.current = null }
  }, [])
  useEffect(() => { inst.current && inst.current.setOption(option, true) }, [option])
  return <div ref={el} style={{ width: '100%', height: '100%', ...style }} />
}
