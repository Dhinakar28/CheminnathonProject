// small client-side helpers
console.log('Equipment Health web UI loaded');

// global error catcher to surface problems (helps debugging client-side failures)
window.addEventListener('error', function(ev) {
	try {
		console.error('Global error caught:', ev.error || ev.message, ev);
		alert('Client error: ' + (ev.message || ev.error && ev.error.toString() || 'see console'));
	} catch(e) { console.warn('error handler failed', e); }
});
window.addEventListener('unhandledrejection', function(ev) {
	try {
		console.error('Unhandled promise rejection:', ev.reason);
		alert('Client promise error: ' + (ev.reason && ev.reason.toString ? ev.reason.toString() : JSON.stringify(ev.reason)));
	} catch(e) { console.warn('unhandledrejection handler failed', e); }
});

// Theme toggle: persist preference in localStorage and update body class
function applyTheme(isDark) {
	try {
		if (isDark) document.body.classList.add('dark'); else document.body.classList.remove('dark');
		localStorage.setItem('eh_theme_dark', isDark ? '1' : '0');
		// update any chart colors by re-drawing summaries if open
		if (window.lastInferenceResult && typeof window.renderResults === 'function') {
			// small delay to allow CSS variables to apply
			setTimeout(()=>{ try { window.renderResults(window.lastInferenceResult, null); } catch(e){ console.warn('renderResults after theme change failed', e); } }, 80);
		}
	} catch(e) { console.warn('applyTheme failed', e); }
}

document.addEventListener('DOMContentLoaded', () => {
	try {
		const t = localStorage.getItem('eh_theme_dark');
		const isDark = t === '1';
		const toggle = document.getElementById('themeToggle');
		if (toggle) {
			toggle.checked = isDark;
			toggle.addEventListener('change', (ev) => applyTheme(ev.target.checked));
		}
		applyTheme(isDark);
	} catch(e) { console.warn('theme init failed', e); }
});

function setGlobalStatus(text, level) {
	const el = document.getElementById('globalStatus');
	if (!el) return;
	el.innerText = text;
	el.className = 'status-badge';
	if (level === 'good') el.classList.add('status-good');
	else if (level === 'warn') el.classList.add('status-warn');
	else if (level === 'crit') el.classList.add('status-crit');
}

// store the last inference response so modals can access it
window.lastInferenceResult = null;
// store the last inference file path for fetching server-side series plots
window.lastInferenceFilePath = null;

// helper to programmatically show a Bootstrap modal by id
window.showModal = function(modalId) {
	try {
		const el = document.getElementById(modalId);
		if (!el) { console.warn('showModal: modal not found', modalId); return; }
		const inst = bootstrap.Modal.getOrCreateInstance(el);
		inst.show();
	} catch (e) { console.warn('showModal failed', modalId, e); }
};

function renderAnomalyDetails(detailObj) {
	// detailObj is expected to be an array of objects: {index, score, snapshot: {col:val...}, top_features: [{feature, z_score}]}
	const area = document.getElementById('anomDetailsArea');
	if (!area) return;
	if (!detailObj || !detailObj.length) {
		area.innerHTML = '<div class="text-muted">No anomalous rows to show.</div>';
		return;
	}
	// create a compact card for each top anomalous row
	const parts = detailObj.map(d => {
		const snap = d.snapshot || {};
		const snapHtml = Object.keys(snap).slice(0,8).map(k => `<div class="small"><strong>${k}</strong>: ${Number(snap[k]).toFixed(3)}</div>`).join('');
		const topFeat = (d.top_features || []).slice(0,5).map(tf => `<li>${tf.feature} (<code>${Number(tf.z_score).toFixed(2)}</code>)</li>`).join('');
		return `<div class="card mb-2"><div class="card-body"><div class="d-flex justify-content-between"><div><strong>Row: ${d.index}</strong><div class="small text-muted">score: ${Number(d.score).toFixed(4)}</div></div><div><small>Top features</small><ul class="mb-0">${topFeat}</ul></div></div><hr>${snapHtml}</div></div>`;
	});
	area.innerHTML = parts.join('');
}

function renderAnomalySuggestions(suggestions) {
	const ul = document.getElementById('anomSuggestions');
	if (!ul) return;
	ul.innerHTML = '';
	if (!suggestions || !suggestions.length) {
		ul.innerHTML = '<li class="text-muted">No suggestions available.</li>';
		return;
	}
	suggestions.forEach(s => {
		const li = document.createElement('li');
		li.innerText = s;
		ul.appendChild(li);
	});
}

// wire modal show event to populate details from lastInferenceResult
document.addEventListener('DOMContentLoaded', () => {
	try {
		const anomModal = document.getElementById('anomModal');
		if (!anomModal) return;
		anomModal.addEventListener('show.bs.modal', (ev) => {
			const j = window.lastInferenceResult;
			if (!j || !j.anom) {
				renderAnomalyDetails([]);
				renderAnomalySuggestions([]);
				return;
			}
			renderAnomalyDetails(j.anom.details || []);
			renderAnomalySuggestions(j.anom.suggestions || []);
		});
	} catch (e) { console.warn('anomaly modal wiring failed', e); }
});

// populate classifier modal
document.addEventListener('DOMContentLoaded', () => {
	try {
		const clfModal = document.getElementById('clfModal');
		if (!clfModal) return;
		clfModal.addEventListener('show.bs.modal', (ev) => {
			const j = window.lastInferenceResult;
			const area = document.getElementById('clfDetailsArea');
			const top = document.getElementById('clfTopModes');
			if (!area || !top) return;
			if (!j || !j.clf) {
				area.innerHTML = '<div class="text-muted">No classifier output</div>';
				top.innerHTML = '';
				return;
			}
			area.innerHTML = `<pre>${JSON.stringify(j.clf.summary || {}, null, 2)}</pre>`;
			const modes = j.clf.summary && j.clf.summary.top_modes ? j.clf.summary.top_modes : [];
			if (!modes.length) top.innerHTML = '<div class="text-muted">No top modes</div>';
			else top.innerHTML = modes.map(m=>`<div><strong>${m.mode}</strong> — ${m.count} rows (${((m.count/(j.clf.summary.n_samples||1))*100).toFixed(1)}%)</div>`).join('');
		});
	} catch (e) { console.warn('clf modal wiring failed', e); }
});

// populate RUL modal
document.addEventListener('DOMContentLoaded', () => {
	try {
		const rulModal = document.getElementById('rulModal');
		if (!rulModal) return;
		rulModal.addEventListener('show.bs.modal', (ev) => {
			const j = window.lastInferenceResult;
			const area = document.getElementById('rulDetailsArea');
			if (!area) return;
			if (!j || !j.rul) { area.innerHTML = '<div class="text-muted">No RUL output</div>'; return; }
			area.innerHTML = `<pre>${JSON.stringify(j.rul.summary || {}, null, 2)}</pre>`;
			// render chart
			try {
				const ctx = document.getElementById('rulModalChart').getContext('2d');
				const bins = j.rul.summary.hist_bins || [];
				const counts = j.rul.summary.hist_counts || [];
				if (window._rulModalChart) window._rulModalChart.destroy();
				window._rulModalChart = new Chart(ctx, {type:'bar', data:{labels:bins, datasets:[{label:'RUL counts', data:counts, backgroundColor:'#9C27B0'}]}, options:{scales:{x:{ticks:{maxRotation:90, minRotation:30}}}}});
			} catch(e) { console.warn('rul chart failed', e); }
		});
	} catch (e) { console.warn('rul modal wiring failed', e); }
});

// populate maintenance modal
document.addEventListener('DOMContentLoaded', () => {
	try {
		const maintModal = document.getElementById('maintModal');
		if (!maintModal) return;
		maintModal.addEventListener('show.bs.modal', (ev) => {
			const j = window.lastInferenceResult;
			const status = document.getElementById('maintStatus');
			const parts = document.getElementById('maintParts');
			const details = document.getElementById('maintDetails');
			if (!status || !parts || !details) return;
			if (!j) { status.innerHTML = '<div class="text-muted">No report available</div>'; parts.innerHTML=''; details.innerHTML=''; return; }
			status.innerHTML = `<div>${j.overall_status || 'Unknown'}</div>`;
			// infer parts from classifier top modes and anomaly details
			parts.innerHTML = '';
			const likely = new Set();
			if (j.clf && j.clf.summary && j.clf.summary.top_modes) {
				j.clf.summary.top_modes.slice(0,3).forEach(m=> likely.add(m.mode));
			}
			// also check top anomalous features
			if (j.anom && j.anom.details) {
				(j.anom.details||[]).slice(0,5).forEach(d => {
					(d.top_features||[]).slice(0,3).forEach(tf => {
						// convert feature names heuristically to parts
						if (/bearing|rotor|shaft|gear|vib/i.test(tf.feature)) likely.add('bearing/rotor');
						else if (/temp|heat|therm/i.test(tf.feature)) likely.add('cooling/thermal');
						else if (/power|voltage|current|amp/i.test(tf.feature)) likely.add('electrical');
						else likely.add(tf.feature);
					});
				});
			}
			if (!likely.size) parts.innerHTML = '<li class="text-muted">No specific part identified</li>';
			else parts.innerHTML = Array.from(likely).map(p=>`<li>${p}</li>`).join('');
			details.innerHTML = `<pre>${JSON.stringify(j.report || [], null, 2)}</pre>`;
		});
	} catch (e) { console.warn('maintenance modal wiring failed', e); }
});

	// populate summaries tabbed modal
	document.addEventListener('DOMContentLoaded', () => {
		try {
			const summaryModal = document.getElementById('summaryModal');
			if (!summaryModal) return;
			summaryModal.addEventListener('show.bs.modal', (ev) => {
				const j = window.lastInferenceResult;
				// if there's no inference result, show a friendly message and return early
				if (!j) {
					try {
						const aSum = document.getElementById('modalAnomSummary');
						const cSum = document.getElementById('modalClfSummary');
						const rSum = document.getElementById('modalRulSummary');
						const aDetails = document.getElementById('modalAnomDetails');
						const cTop = document.getElementById('modalClfTopModes');
						const rSamples = document.getElementById('modalRulSamples');
						if (aSum) aSum.innerHTML = '<div class="text-muted">No inference results yet. Run inference first.</div>';
						if (cSum) cSum.innerHTML = '<div class="text-muted">No inference results yet. Run inference first.</div>';
						if (rSum) rSum.innerHTML = '<div class="text-muted">No inference results yet. Run inference first.</div>';
						if (aDetails) aDetails.innerHTML = '';
						if (cTop) cTop.innerHTML = '';
						if (rSamples) rSamples.innerHTML = '';
					} catch (e) { console.warn('summary modal fallback fill failed', e); }
					return;
				}
				// Anomaly tab
				const aSum = document.getElementById('modalAnomSummary');
				const aDetails = document.getElementById('modalAnomDetails');
				const aCtxEl = document.getElementById('modalAnomChart');
				if (aSum) aSum.innerHTML = j && j.anom ? `<pre>${JSON.stringify(j.anom.summary || {}, null, 2)}</pre>` : '<div class="text-muted">No anomaly</div>';
				if (aDetails) aDetails.innerHTML = j && j.anom ? '' : '';
				// if Chart isn't loaded yet, skip drawing charts and show a note
				const chartAvailable = (typeof Chart !== 'undefined');
				if (!chartAvailable) {
					try {
						const note = '<div class="text-warning">Charts unavailable. Reload the page if this persists.</div>';
						if (aCtxEl) aCtxEl.replaceWith(document.createElement('div'));
						const aCtxWrap = document.getElementById('pane-anom');
						if (aCtxWrap && aCtxWrap.querySelector) {
							const el = aCtxWrap.querySelector('#modalAnomChart');
							if (el && el.parentNode) el.parentNode.innerHTML = '<div class="text-muted">Chart disabled</div>' + note;
						}
					} catch (e) { console.warn('fallback anom chart handling failed', e); }
				} else {
					try {
						if (aCtxEl && j && j.anom) {
							const ctx = aCtxEl.getContext('2d');
							const anomCount = j.anom.summary ? j.anom.summary.n_anomalies : 0;
							const normalCount = j.anom.summary ? j.anom.summary.n_samples - anomCount : 0;
							if (window._modalAnomChart) window._modalAnomChart.destroy();
							window._modalAnomChart = new Chart(ctx, {type:'pie', data:{labels:['Normal','Anomaly'], datasets:[{data:[normalCount, anomCount], backgroundColor:['#4CAF50','#F44336']} ]}});
						}
					} catch(e){ console.warn('modal anom chart fail', e); }
				}

				// Classifier tab
				const cSum = document.getElementById('modalClfSummary');
				const cTop = document.getElementById('modalClfTopModes');
				const cCtxEl = document.getElementById('modalClfChart');
				if (cSum) cSum.innerHTML = j && j.clf ? `<pre>${JSON.stringify(j.clf.summary || {}, null, 2)}</pre>` : '<div class="text-muted">No classifier</div>';
				if (cTop) cTop.innerHTML = j && j.clf && j.clf.summary && j.clf.summary.top_modes ? j.clf.summary.top_modes.map(m=>`<div><strong>${m.mode}</strong> — ${m.count}</div>`).join('') : '<div class="text-muted">No top modes</div>';
				if (!chartAvailable) {
					try {
						if (cCtxEl && cCtxEl.parentNode) cCtxEl.parentNode.innerHTML = '<div class="text-muted">Chart disabled</div>';
					} catch(e){ console.warn('fallback clf chart handling failed', e); }
				} else {
					try {
						if (cCtxEl && j && j.clf) {
							const ctx = cCtxEl.getContext('2d');
							const counts = j.clf.summary && j.clf.summary.counts ? j.clf.summary.counts : {};
							const labels = Object.keys(counts);
							const vals = labels.map(l=>counts[l]);
							if (window._modalClfChart) window._modalClfChart.destroy();
							window._modalClfChart = new Chart(ctx, {type:'bar', data:{labels, datasets:[{label:'Count', data:vals, backgroundColor:'#2196F3'}]}});
						}
					} catch(e){ console.warn('modal clf chart fail', e); }
				}

				// RUL tab
				const rSum = document.getElementById('modalRulSummary');
				const rSamples = document.getElementById('modalRulSamples');
				const rCtxEl = document.getElementById('modalRulChart');
				if (rSum) rSum.innerHTML = j && j.rul ? `<pre>${JSON.stringify(j.rul.summary || {}, null, 2)}</pre>` : '<div class="text-muted">No RUL</div>';
				if (rSamples) rSamples.innerHTML = j && j.rul && j.rul.sample_preds ? `<pre>${JSON.stringify(j.rul.sample_preds.slice(0,20) || [], null, 2)}</pre>` : '<div class="text-muted">No samples</div>';
				if (!chartAvailable) {
					try { if (rCtxEl && rCtxEl.parentNode) rCtxEl.parentNode.innerHTML = '<div class="text-muted">Chart disabled</div>';} catch(e){ console.warn('fallback rul chart failed', e); }
				} else {
					try {
						if (rCtxEl && j && j.rul) {
							const ctx = rCtxEl.getContext('2d');
							const bins = j.rul.summary && j.rul.summary.hist_bins ? j.rul.summary.hist_bins : [];
							const counts = j.rul.summary && j.rul.summary.hist_counts ? j.rul.summary.hist_counts : [];
							if (window._modalRulChart) window._modalRulChart.destroy();
							window._modalRulChart = new Chart(ctx, {type:'bar', data:{labels:bins, datasets:[{label:'RUL counts', data:counts, backgroundColor:'#9C27B0'}]}, options:{scales:{x:{ticks:{maxRotation:90}}}}});
						}
					} catch(e){ console.warn('modal rul chart fail', e); }
				}
			});
		} catch (e) { console.warn('summary modal wiring failed', e); }
	});

// When upload completes, unhide main content area
function onUploadLoaded(summary, file_path, stem) {
	try {
		const main = document.getElementById('mainContent');
		if (main) main.classList.remove('d-none');
		// display uploaded summary in uploadSummaryArea
		const area = document.getElementById('uploadSummaryArea');
		if (area && summary) area.innerHTML = `<p>Rows: ${summary.n_rows} — Numeric: ${summary.n_numeric}</p><p>Cols: ${summary.numeric_cols ? summary.numeric_cols.slice(0,10).join(', ') : ''}</p><button id="runBtn" class="btn btn-success">Run Inference</button>`;
		// rebind runBtn (since we replaced it)
		const runBtn = document.getElementById('runBtn');
		if (runBtn) runBtn.addEventListener('click', async () => {
			// trigger the same logic as original run handler by dispatching a click on the original run button
			runBtn.disabled = true;
			runBtn.innerText = 'Running...';
			// call run_inference endpoint
			const resp = await fetch('/run_inference', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({file_path, stem})});
			const j = await resp.json();
			window.lastInferenceResult = j;
			try { window.lastInferenceFilePath = file_path || window.lastUploadFilePath || null; } catch(e) { window.lastInferenceFilePath = null; }
			// restore label
			runBtn.disabled = false; runBtn.innerText = 'Run Inference';
			// render full results (populates reportArea, summaries, charts and visuals)
			try { if (typeof window.renderResults === 'function') window.renderResults(j, file_path); else console.warn('renderResults not defined'); } catch(e) { console.warn(e); }
		});
	} catch (e) { console.warn('onUploadLoaded failed', e); }
}

// renderResults: populate the page from an inference JSON
window.renderResults = function(j, file_path) {
	try {
		window.lastInferenceResult = j;
	document.getElementById('results').classList.remove('d-none');
		// report
		const reportArea = document.getElementById('reportArea');
		if (reportArea) reportArea.innerHTML = j.report ? j.report.map(r=>`<div>${r}</div>`).join('') : '<div class="text-muted">No report</div>';
		// quick summary
		const quick = [];
		if (j.anom && j.anom.summary) quick.push(`Anomaly rate: ${(j.anom.summary.anomaly_rate*100).toFixed(2)}% (${j.anom.summary.n_anomalies}/${j.anom.summary.n_samples})`);
		if (j.rul && j.rul.summary) quick.push(`RUL median: ${j.rul.summary.median !== null ? j.rul.summary.median.toFixed(1) : 'N/A'}`);
		if (j.clf && j.clf.summary) quick.push(j.clf.summary.top_class ? `Top predicted mode: ${j.clf.summary.top_class}` : 'No classifier output');
		const quickEl = document.getElementById('quickSummary'); if (quickEl) quickEl.innerHTML = quick.map(x=>`<div>${x}</div>`).join('');
		// metrics
		const metricsRow = document.getElementById('metricsRow'); if (metricsRow) metricsRow.classList.remove('d-none');
		const tileAnom = document.getElementById('tileAnom'); const tileTop = document.getElementById('tileTopMode'); const tileRUL = document.getElementById('tileRUL');
		if (tileAnom) tileAnom.innerText = j.anom && j.anom.summary ? `${(j.anom.summary.anomaly_rate*100).toFixed(2)} %` : '-';
		if (tileTop) {
			try {
				// prefer top_modes (readable labels), fall back to readable_counts, then top_class (explicitly allow 0)
				const cs = j.clf && j.clf.summary ? j.clf.summary : null;
				if (cs && cs.top_modes && cs.top_modes.length) {
					const m = cs.top_modes[0];
					const pct = cs.n_samples ? ((m.count / cs.n_samples) * 100).toFixed(1) : '0.0';
					tileTop.innerText = `${m.mode} · ${m.count} (${pct}%)`;
				} else if (cs && cs.readable_counts) {
					// pick highest-count readable label
					const entries = Object.entries(cs.readable_counts || {});
					if (entries.length) {
						entries.sort((a,b)=>b[1]-a[1]);
						const top = entries[0];
						const pct = cs.n_samples ? ((top[1] / cs.n_samples) * 100).toFixed(1) : '0.0';
						tileTop.innerText = `${top[0]} · ${top[1]} (${pct}%)`;
					} else {
						tileTop.innerText = '-';
					}
				} else if (cs && typeof cs.top_class !== 'undefined' && cs.top_class !== null) {
					const tc = cs.top_class;
					const cnt = cs.counts && cs.counts[String(tc)] ? cs.counts[String(tc)] : 0;
					const pct = cs.n_samples ? ((cnt / cs.n_samples) * 100).toFixed(1) : '0.0';
					tileTop.innerText = `${tc} · ${cnt} (${pct}%)`;
				} else {
					tileTop.innerText = '-';
				}
			} catch(e) { tileTop.innerText = '-'; console.warn('tileTop render failed', e); }
		}
		if (tileRUL) tileRUL.innerText = j.rul && j.rul.summary && j.rul.summary.median !== null ? `${j.rul.summary.median.toFixed(1)} cycles` : '-';
		// details blocks
		const anomSummary = document.getElementById('anomSummary'); if (anomSummary) anomSummary.innerHTML = j.anom ? `<pre>${JSON.stringify(j.anom.summary, null, 2)}</pre>` : 'No anomaly model';
		const clfSummary = document.getElementById('clfSummary'); if (clfSummary) clfSummary.innerHTML = j.clf ? `<pre>${JSON.stringify(j.clf.summary, null, 2)}</pre>` : 'No classifier model';
		const rulSummary = document.getElementById('rulSummary'); if (rulSummary) rulSummary.innerHTML = j.rul ? `<pre>${JSON.stringify(j.rul.summary, null, 2)}</pre>` : 'No RUL model';

		// maintenance card accent based on maintenance_level returned by server
		try {
			const maintCard = document.getElementById('maintenanceCard');
			const maintBadge = document.getElementById('maintenanceBadge');
			if (maintCard) {
				maintCard.classList.remove('maint-good','maint-normal','maint-critical');
				const lvl = j.maintenance_level || 'good';
				if (lvl === 'critical') maintCard.classList.add('maint-critical');
				else if (lvl === 'normal') maintCard.classList.add('maint-normal');
				else maintCard.classList.add('maint-good');
			}
			if (maintBadge) {
				if (j.maintenance_level === 'critical') { maintBadge.innerText = 'CRITICAL'; maintBadge.className = 'maint-badge bg-danger text-white'; }
				else if (j.maintenance_level === 'normal') { maintBadge.innerText = 'NORMAL'; maintBadge.className = 'maint-badge bg-warning text-dark'; }
				else { maintBadge.innerText = 'GOOD'; maintBadge.className = 'maint-badge bg-success text-white'; }
			}
		} catch(e) { console.warn('maintenance card apply failed', e); }
	// series plot (image is prepared; rendering of charts is done on-demand in Visuals modal)
		try {
			const numericCols = j.clf && j.clf.meta && j.clf.meta.feature_columns ? j.clf.meta.feature_columns : (j.anom && j.anom.meta && j.anom.meta.feature_columns ? j.anom.meta.feature_columns : null);
			const img = document.getElementById('seriesPlot');
			if (img && file_path && numericCols && numericCols.length) {
				// fetch as blob to detect JSON errors
				fetch(`/plot_series.png?file_path=${encodeURIComponent(file_path)}&col=${encodeURIComponent(numericCols[0])}`).then(r=>{
					const ct = r.headers.get('content-type')||'';
					if (ct.startsWith('image')) return r.blob().then(b=>{ img.src = URL.createObjectURL(b); });
					return r.json().then(j=>{ img.alt = 'plot error'; img.src = ''; console.warn('plot error', j); });
				}).catch(e=>{ console.warn('plot fetch failed', e); });
			}
		} catch(e) { console.warn(e); }
		// charts are rendered on-demand by renderVisuals when Visuals modal opens
	} catch (e) { console.warn('renderResults failed', e); }
};

// draw charts and series image into the Visuals modal when requested
window.renderVisuals = function(j, file_path) {
	try {
		if (!j) return;
		// series plot image
		try {
			const numericCols = j.clf && j.clf.meta && j.clf.meta.feature_columns ? j.clf.meta.feature_columns : (j.anom && j.anom.meta && j.anom.meta.feature_columns ? j.anom.meta.feature_columns : null);
			const img = document.getElementById('seriesPlot');
			if (img && file_path && numericCols && numericCols.length) {
				fetch(`/plot_series.png?file_path=${encodeURIComponent(file_path)}&col=${encodeURIComponent(numericCols[0])}`).then(r=>{
					const ct = r.headers.get('content-type')||'';
					if (ct.startsWith('image')) return r.blob().then(b=>{ img.src = URL.createObjectURL(b); });
					return r.json().then(j=>{ img.alt = 'plot error'; img.src = ''; console.warn('plot error', j); });
				}).catch(e=>{ console.warn('plot fetch failed', e); });
			}
		} catch(e) { console.warn('series plot in renderVisuals failed', e); }

		// ensure Chart.js available
		if (typeof Chart === 'undefined') { console.warn('Chart.js is not available'); return; }

		// anomaly pie
		try {
			const ctx = document.getElementById('anomChart').getContext('2d');
			const anom = j.anom;
			const anomCount = anom && anom.summary ? anom.summary.n_anomalies : 0;
			const normalCount = anom && anom.summary ? anom.summary.n_samples - anomCount : 0;
			const dataA = {labels:['Normal','Anomaly'], datasets:[{data:[normalCount, anomCount], backgroundColor:['#4CAF50','#F44336']}]};
			if (window.anomChartObj) window.anomChartObj.destroy();
			window.anomChartObj = new Chart(ctx, {type:'pie', data: dataA});
		} catch(e) { console.warn('anom chart draw failed', e); }

		// classifier bar
		try {
			const clfCtx = document.getElementById('clfChart').getContext('2d');
			const counts = j.clf && j.clf.summary && j.clf.summary.counts ? j.clf.summary.counts : {};
			const labels = Object.keys(counts);
			const values = labels.map(l=>counts[l]);
			if (window.clfChartObj) window.clfChartObj.destroy();
			window.clfChartObj = new Chart(clfCtx, {type:'bar', data:{labels, datasets:[{label:'Count', data:values, backgroundColor:'#2196F3'}]}});
		} catch(e) { console.warn('clf chart draw failed', e); }

		// rul histogram
		try {
			const rulCtx = document.getElementById('rulChart').getContext('2d');
			const bins = j.rul && j.rul.summary ? j.rul.summary.hist_bins : [];
			const countsR = j.rul && j.rul.summary ? j.rul.summary.hist_counts : [];
			if (window.rulChartObj) window.rulChartObj.destroy();
			window.rulChartObj = new Chart(rulCtx, {type:'bar', data:{labels:bins, datasets:[{label:'RUL counts', data:countsR, backgroundColor:'#9C27B0'}]}, options:{scales:{x:{ticks:{maxRotation:90, minRotation:30}}}}});
		} catch(e) { console.warn('rul chart draw failed', e); }

	} catch(e) { console.warn('renderVisuals failed', e); }
}

// wire visuals modal to draw charts when opened
document.addEventListener('DOMContentLoaded', () => {
	try {
		const visModal = document.getElementById('visualsModal');
		if (!visModal) return;
		visModal.addEventListener('show.bs.modal', (ev) => {
			try {
				// prefer explicit persisted file path, then fallback to any path stored on the lastInferenceResult, then null
				const fp = window.lastInferenceFilePath || (window.lastInferenceResult && window.lastInferenceResult._file_path) || null;
				window.renderVisuals(window.lastInferenceResult, fp);
			} catch(e) { console.warn('visuals modal render failed', e); }
		});
	} catch(e) { console.warn('visuals modal wiring failed', e); }
});

	// Ensure modal buttons reliably open their modals (fallback if data-bs attributes fail or buttons are inside forms)
	document.addEventListener('DOMContentLoaded', () => {
		try {
			const targets = ['#visualsModal','#summaryModal','#anomModal','#clfModal','#rulModal','#maintModal'];
			targets.forEach(t => {
				const selector = `[data-bs-target="${t}"]`;
				document.querySelectorAll(selector).forEach(btn => {
					// make sure clicking doesn't submit an outer form
					btn.addEventListener('click', (ev) => {
						try { ev.preventDefault(); } catch(e) {}
						const modalEl = document.querySelector(t);
						if (!modalEl) return;
						try {
							const inst = bootstrap.Modal.getOrCreateInstance(modalEl);
							inst.show();
						} catch(e) { console.warn('programmatic modal show failed', e); }
					});
				});
			});
		} catch(e) { console.warn('modal button wiring failed', e); }
	});
