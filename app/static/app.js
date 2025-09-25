// small client-side helpers
console.log('Equipment Health web UI loaded');

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
		document.getElementById('visuals').classList.remove('d-none');
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
		if (tileTop) tileTop.innerText = j.clf && j.clf.summary && j.clf.summary.top_class ? j.clf.summary.top_class : '-';
		if (tileRUL) tileRUL.innerText = j.rul && j.rul.summary && j.rul.summary.median !== null ? `${j.rul.summary.median.toFixed(1)} cycles` : '-';
		// details blocks
		const anomSummary = document.getElementById('anomSummary'); if (anomSummary) anomSummary.innerHTML = j.anom ? `<pre>${JSON.stringify(j.anom.summary, null, 2)}</pre>` : 'No anomaly model';
		const clfSummary = document.getElementById('clfSummary'); if (clfSummary) clfSummary.innerHTML = j.clf ? `<pre>${JSON.stringify(j.clf.summary, null, 2)}</pre>` : 'No classifier model';
		const rulSummary = document.getElementById('rulSummary'); if (rulSummary) rulSummary.innerHTML = j.rul ? `<pre>${JSON.stringify(j.rul.summary, null, 2)}</pre>` : 'No RUL model';
		// series plot
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
		// charts
		try {
			// anomaly pie
			const ctx = document.getElementById('anomChart').getContext('2d');
			const anom = j.anom;
			const anomCount = anom && anom.summary ? anom.summary.n_anomalies : 0;
			const normalCount = anom && anom.summary ? anom.summary.n_samples - anomCount : 0;
			const dataA = {labels:['Normal','Anomaly'], datasets:[{data:[normalCount, anomCount], backgroundColor:['#4CAF50','#F44336']}]};
			if (window.anomChartObj) window.anomChartObj.destroy();
			window.anomChartObj = new Chart(ctx, {type:'pie', data: dataA});
			// classifier bar chart
			const clfCtx = document.getElementById('clfChart').getContext('2d');
			const counts = j.clf && j.clf.summary && j.clf.summary.counts ? j.clf.summary.counts : {};
			const labels = Object.keys(counts);
			const values = labels.map(l=>counts[l]);
			if (window.clfChartObj) window.clfChartObj.destroy();
			window.clfChartObj = new Chart(clfCtx, {type:'bar', data:{labels, datasets:[{label:'Count', data:values, backgroundColor:'#2196F3'}]}});
			// rul histogram
			const rulCtx = document.getElementById('rulChart').getContext('2d');
			const bins = j.rul && j.rul.summary ? j.rul.summary.hist_bins : [];
			const countsR = j.rul && j.rul.summary ? j.rul.summary.hist_counts : [];
			if (window.rulChartObj) window.rulChartObj.destroy();
			window.rulChartObj = new Chart(rulCtx, {type:'bar', data:{labels:bins, datasets:[{label:'RUL counts', data:countsR, backgroundColor:'#9C27B0'}]}, options:{scales:{x:{ticks:{maxRotation:90, minRotation:30}}}}});
		} catch(e) { console.warn(e); }
	} catch (e) { console.warn('renderResults failed', e); }
};
