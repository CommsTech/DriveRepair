"""Standalone, offline, evidence-led DriveRepair HTML report.

Inspired by the *level of detail*, not the graphics or proprietary layout, of
GRC's publicly documented ValiDrive report. Never manufacture a health score,
validated capacity, latencies or full-surface coverage from sparse samples.
"""
from __future__ import annotations

import html
from pathlib import Path
from datetime import datetime, timezone


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _bytes(value) -> str:
    if not isinstance(value, (float, int)) or value < 0:
        return 'Not measured'
    size=float(value)
    for unit in ('B','KiB','MiB','GiB','TiB'):
        if size<1024 or unit=='TiB':
            return f'{size:,.0f} {unit}' if unit=='B' else f'{size:,.2f} {unit}'
        size/=1024
    return 'Not measured'


def _metric(name, value, detail=''):
    return (f'<div class="metric"><div class="label">{_esc(name)}</div>'
            f'<div class="value">{_esc(value)}</div><div class="sub">{_esc(detail)}</div></div>')


def _palette(status: str) -> str:
    return {'validated':'#34c7ad','readable':'#34c7ad','sampled':'#56a8b9','mismatch':'#fb7586',
            'restoration_error':'#fb7586','read_error':'#efad60',
            'write_error':'#e08088','unstable_original':'#f0c66e',
            'slow':'#f0c66e','untested':'#253b53'}.get(status,'#253b53')


def _map(regions: list[dict], *, columns: int=24) -> str:
    if not regions:
        return '<div class="empty">No location-level evidence was retained. A percentage alone cannot reconstruct a surface map.</div>'
    cells=[]
    for i,r in enumerate(regions[:2500]):
        status=str(r.get('status') or 'untested')
        loc=f'Offset {_bytes(r.get("offset"))} · {status.replace("_", " ")}'
        cells.append(f'<span class="cell" style="background:{_palette(status)}" '
                     f'title="{_esc(loc)}" aria-label="{_esc(loc)}"></span>')
    return (f'<div class="heatmap" style="--columns:{columns}" role="img" '
            f'aria-label="Sampled storage location map">{"".join(cells)}</div>')


def _timings(stats: dict | None, title: str) -> str:
    if not isinstance(stats,dict) or not stats:
        return f'<div class="timing"><h3>{_esc(title)}</h3><p class="dim">No latency measurements available</p></div>'
    rows=[('Samples',stats.get('samples')),('Minimum',stats.get('min_ms')),
          ('Median',stats.get('median_ms')),('Average',stats.get('mean_ms')),
          ('Maximum',stats.get('max_ms')),('Std. deviation',stats.get('stddev_ms')),
          ('Coefficient of variation',stats.get('coefficient_of_variation')),
          ('Total',stats.get('total_ms'))]
    body=''.join('<tr><td>'+_esc(label)+'</td><td>'+_esc('—' if value is None else value)+
                 ('' if label in ('Samples','Coefficient of variation') else ' ms')+'</td></tr>'
                 for label,value in rows)
    # A simple pure-CSS visual ratio of median to maximum shows latency spread
    # without implying a continuous measured time series.
    median=stats.get('median_ms')
    worst=stats.get('max_ms')
    ratio=(max(0,min(100,100*median/worst)) if isinstance(median,(int,float))
           and isinstance(worst,(int,float)) and worst>0 else 0)
    graphic=(f'<div class="latencytrack" aria-label="Median latency as fraction of maximum">'
             f'<div class="latencyfill" style="width:{ratio:.2f}%"></div></div>'
             f'<p class="dim">Median / worst observed latency (not sequential speed)</p>')
    return f'<div class="timing"><h3>{_esc(title)}</h3>{graphic}<table><tbody>{body}</tbody></table></div>'


def render_report(result: dict, *, device: dict | None = None, title: str='Storage evidence report',
                  scan_regions: list[dict] | None = None) -> str:
    """Pure, escaped HTML from explicit result fields; no network assets or JS."""
    if not isinstance(result,dict):
        raise ValueError('Report input must be a result dictionary')
    device=device or {}
    kind=str(result.get('test_kind') or ('read_only_scan' if any(k in result for k in ('scan','surface_coverage_pct','readable_bytes')) else 'disk_operation'))
    capacity=kind=='capacity_spot_write_restore'
    status=str(result.get('status') or 'NOT_REPORTED')
    counters=result.get('counters') if isinstance(result.get('counters'),dict) else {}
    scan=result.get('scan') if isinstance(result.get('scan'),dict) else result
    declared=result.get('declared_bytes') if capacity else device.get('size_bytes',scan.get('size_bytes'))
    if capacity:
        validated=counters.get('validated',0)
        planned=result.get('samples_planned',0)
        observed=f'{validated:,} / {planned:,}'
        tested=f'{result.get("samples_completed",0):,} spots'
        failures=sum(int(counters.get(n,0) or 0) for n in ('mismatch','read_error','write_error','unstable_original','restoration_error'))
        verdict=('Evidence of storage failure' if failures else
                 'Spot checks passed, not certified' if status=='SAMPLED_REGIONS_VERIFIED' else
                 'Incomplete validation')
        detail=('Read → save original → write random data → verify → restore → reread. '
                'Raw spot checks can harm existing files if a device lies about its capacity; '
                'a verified sample is not a guaranteed capacity boundary.')
        metric_summary=_metric('Successful spot verifications',observed,'Validated sampled locations')+\
                       _metric('Locations tested',tested,'Distinct positions')+\
                       _metric('Reported capacity',_bytes(declared),'Claimed size, not confirmed capacity')+\
                       _metric('Highest validated address',_bytes(result.get('highest_verified_offset')),
                               'A sample, NOT contiguous validated capacity')
        regions=result.get('regions') or []
    else:
        coverage=scan.get('surface_coverage_pct',result.get('surface_coverage_pct'))
        coverage_text=(f'{coverage:.2f}%' if type(coverage) in (int,float) else 'Unknown')
        failures=scan.get('read_error_chunks',result.get('read_error_chunks'))
        verdict=('Read errors observed' if isinstance(failures,int) and failures else
                 'No read errors reported' if failures==0 else 'Evidence incomplete')
        detail=('A scan measures readable observations, not file checksums, remaining lifespan '
                'or physical-media repair. Unvisited locations remain unknown.')
        metric_summary=_metric('Successful read coverage',coverage_text,'Of claimed physical address space')+\
                       _metric('Readable bytes',_bytes(scan.get('readable_bytes')),'Confirmed successful read operations')+\
                       _metric('Failed read requests',failures if failures is not None else 'Unknown','Not confirmed bad sectors')+\
                       _metric('Declared capacity',_bytes(declared),'Device-advertised capacity')
        regions=scan_regions or []
    meta=[('Model',device.get('model') or 'Unknown'),('Bus',device.get('bus') or 'Unknown'),
          ('Serial suffix',device.get('serial_suffix') or 'Unavailable'),
          ('Logical sector size',device.get('sector_size') or 'Unknown'),
          ('Workflow',kind.replace('_',' ').title()),('Result code',status),
          ('Generated at',datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))]
    meta_html=''.join(f'<div><span>{_esc(k)}</span><strong>{_esc(v)}</strong></div>' for k,v in meta)
    legend=''.join(f'<span><i style="background:{_palette(k)}"></i>{_esc(label)}</span>' for k,label in
                   [('validated' if capacity else 'readable','Verified sample' if capacity else 'Readable'),
                    ('read_error','Read issue'),('mismatch','Mismatch'),('untested','Not tested')])
    rows=''.join(f'<tr><td>{i+1}</td><td>{_esc(_bytes(r.get("offset")))}</td>'
                 f'<td>{_esc(_bytes(r.get("length")))}</td><td><b class="dot" '
                 f'style="background:{_palette(str(r.get("status")))}"></b>'
                 f'{_esc(str(r.get("status", "unknown")).replace("_", " ").title())}</td></tr>'
                 for i,r in enumerate(regions[:1000]))
    breakdown=''.join(f'<div><span class="dot" style="background:{_palette(str(k))}"></span>'
                      f'<span>{_esc(k.replace("_"," ").title())}</span><strong>{_esc(v)}</strong></div>'
                      for k,v in counters.items()) if capacity else '<p class="dim">Read-only results do not include write-capacity sampling.</p>'
    latency=(_timings(result.get('read_latency'),'Read latency')+
             _timings(result.get('write_latency'),'Write latency')) if capacity else ''
    # SMART evidence: attributes are vendor-defined; thresholds and normalised
    # values are shown with their source, never converted into "life remaining".
    attributes = result.get('ata_attributes') if isinstance(result.get('ata_attributes'), list) else []
    logs = result.get('smart_logs') if isinstance(result.get('smart_logs'), dict) else {}
    smart_section = ''
    if attributes or logs.get('available'):
        rows = ''.join(
            '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                _esc(entry.get('id')), _esc(entry.get('name')),
                _esc(entry.get('value')), _esc(entry.get('worst')),
                _esc(entry.get('thresh')),
                _esc(entry.get('raw_string') if entry.get('raw_string') is not None
                     else entry.get('raw_value')))
            for entry in attributes[:64])
        selftest = logs.get('selftest') or {}
        error_log = logs.get('error_log') or {}
        log_text = ' '.join(filter(None, [
            (f"Self-test log: {selftest.get('count')} entries." if selftest.get('available') else
             f"Self-test log unavailable ({selftest.get('reason', 'not reported')})."),
            (f"Error log: {error_log.get('count')} entries." if error_log.get('available') else
             f"Error log unavailable ({error_log.get('reason', 'not reported')})."),
        ]))
        smart_section = ('<section class="panel"><h2>SMART evidence</h2>'
                         '<p class="dim">Vendor-defined attributes, read only. '
                         'A normalised value near its threshold is not a prediction of failure, '
                         'and no self-test was started by this report.</p>'
                         '<div class="tablewrap"><table><thead><tr><th>ID</th><th>Attribute</th>'
                         '<th>Value</th><th>Worst</th><th>Threshold</th><th>Raw</th></tr></thead><tbody>'
                         + (rows or '<tr><td colspan="6">No attributes returned</td></tr>')
                         + '</tbody></table></div><p class="dim">' + _esc(log_text) + '</p></section>')
    conclusion=('Stop using this device for important data. If personal data was present, restore from '
                'backup or use an appropriate professional lab.' if capacity and failures else
                'Spot tests found no sampled mismatch. Use a full-capacity verification on disposable media '
                'and preserve backups; passing spots cannot certify all storage.' if capacity else
                'If data is important or errors occurred, create a separate recovery image before attempting writes.')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>'''+_esc(title)+''' · DriveRepair</title><style>
:root{color-scheme:dark;--bg:#0b1521;--surface:#142439;--surface2:#1b3048;--border:#30445a;--text:#f2f7fe;--sub:#b0c2d4;--teal:#40cfb5;--red:#fb7586;--amber:#f1b45e}
*{box-sizing:border-box}body{background:var(--bg);color:var(--text);font:14px/1.55 'Segoe UI',Inter,system-ui,sans-serif;margin:0}
main{max-width:1200px;margin:auto;padding:42px 30px 64px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;border-bottom:1px solid var(--border);padding-bottom:20px;margin-bottom:32px}.logo{font-weight:800;letter-spacing:.12em;color:var(--teal)}.eyebrow{color:var(--sub);font-size:11px;text-transform:uppercase;letter-spacing:.16em;font-weight:750}
h1{font-size:34px;letter-spacing:-.04em;line-height:1.15;margin:8px 0 10px}.muted,.dim{color:var(--sub)}.hero{display:flex;justify-content:space-between;align-items:flex-start;gap:30px;margin:0 0 30px}.verdict{font-size:20px;font-weight:750;color:var(--amber)}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.metric,.panel{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px}.metric{min-height:126px}.metric .label{color:var(--sub);font-size:12px}.metric .value{font-size:24px;font-weight:760;margin-top:8px;letter-spacing:-.03em}.metric .sub{color:var(--sub);font-size:11px;margin-top:6px}section{margin-top:26px}h2{font-size:18px;margin:0 0 16px}h3{font-size:15px;margin:0 0 12px}.twocol{display:grid;grid-template-columns:2fr 1fr;gap:16px}.heatmap{display:grid;grid-template-columns:repeat(var(--columns),minmax(0,1fr));gap:3px}.cell{min-width:0;height:14px;border-radius:2px;opacity:.97}.cell:hover{outline:2px solid white}.legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:15px;color:var(--sub);font-size:12px}.legend i,.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}.breakdown>div{display:flex;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid #263b53}.breakdown strong{margin-left:auto}.metadata{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.metadata div{display:flex;flex-direction:column;border-bottom:1px solid var(--border);padding-bottom:8px}.metadata span{font-size:12px;color:var(--sub)}table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:10px 12px;border-bottom:1px solid var(--border);text-align:left}th{color:var(--sub)}.tablewrap{max-height:440px;overflow:auto}.timings{flex:1}.timinggrid{display:flex;gap:20px}.latencytrack{height:11px;border-radius:9px;background:#2a4057;overflow:hidden;margin:15px 0 7px}.latencyfill{height:100%;background:linear-gradient(90deg,#328b9c,var(--teal));border-radius:9px}.timing{min-width:0;flex:1}.summary{padding:16px 20px;border-left:4px solid var(--teal);background:var(--surface);border-radius:0 9px 9px 0}.empty{padding:28px;text-align:center;color:var(--sub)}details{margin-top:14px}summary{cursor:pointer;color:var(--teal);font-weight:700;padding:8px 0}details[open] summary{margin-bottom:10px}footer{color:var(--sub);font-size:12px;margin-top:30px}a{color:var(--teal)}
@media(max-width:850px){.grid{grid-template-columns:repeat(2,1fr)}.twocol{grid-template-columns:1fr}.hero{flex-direction:column}.metadata{grid-template-columns:1fr}}@media print{body{background:#fff;color:#17283b;print-color-adjust:exact;-webkit-print-color-adjust:exact}.metric,.panel,.summary{background:#f2f5f9;color:#17283b}main{padding:15px}.tablewrap{max-height:none}.cell{border:1px solid #ddd}}
</style></head><body><main><header class="top"><div class="logo">DR / DRIVEREPAIR</div><div class="eyebrow">LOCAL STORAGE EVIDENCE · NO UPLOADS</div></header>
<div class="hero"><div><div class="eyebrow">Technical evidence report</div><h1>'''+_esc(title)+'''</h1><p class="muted">'''+_esc(detail)+'''</p></div><div><div class="eyebrow">Assessment</div><div class="verdict">'''+_esc(verdict)+'''</div><div class="muted">'''+_esc(status.replace('_',' '))+'''</div></div></div>
<div class="grid">'''+metric_summary+'''</div>
<section class="twocol"><div class="panel"><h2>Sampled address map</h2>'''+_map(regions)+'''<div class="legend">'''+legend+'''</div><p class="dim">Each tile describes one recorded observation, not surrounding untested bytes. Capacity may be spoofed and samples may alias.</p></div><div class="panel"><h2>Evidence breakdown</h2><div class="breakdown">'''+breakdown+'''</div></div></section>
<section class="panel"><h2>Device & session facts</h2><div class="metadata">'''+meta_html+'''</div></section>
'''+('''<section class="panel"><h2>Measured access latency</h2><p class="dim">Small random reads/writes, not sequential throughput. Coefficient of variation = standard deviation / average.</p><div class="timinggrid">'''+latency+'''</div></section>''' if capacity else '')+smart_section+'''
<section class="panel"><h2>Technical location evidence</h2><p class="dim">For specialists: each observation is tied to a specific logical byte offset. A read-only scan may report aggregate cells, not every individual sector.</p><details><summary>Show sampled positions and outcomes</summary><div class="tablewrap"><table><thead><tr><th>#</th><th>Start offset</th><th>Length</th><th>Outcome</th></tr></thead><tbody>'''+(rows or '<tr><td colspan="4">No sampled locations available</td></tr>')+'''</tbody></table></div></details></section>
<section><h2>Recommended next action</h2><div class="summary">'''+_esc(conclusion)+'''</div></section><footer>Generated locally by DriveRepair. Observed data is not a warranty, recovered-file checksum, or estimate of remaining service life. Retain original logs and journals.</footer></main></body></html>'''


def save_report(path: str | Path, result: dict, *, device: dict | None=None,
                scan_regions: list[dict] | None=None) -> Path:
    path=Path(path)
    if path.suffix.lower()!='.html' or path.is_symlink() or path.exists():
        raise ValueError('Choose a NEW .html report path; existing files are not overwritten')
    content=render_report(result, device=device, scan_regions=scan_regions)
    with path.open('x',encoding='utf-8') as handle:
        handle.write(content)
    return path
