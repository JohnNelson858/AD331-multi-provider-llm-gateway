'use strict';
const $ = id => document.getElementById(id);
let models = [], controller = null;
const emptyResponse = 'Your streamed response will appear here.';
function setModels() {
  $('model').replaceChildren(...models.filter(m => m.provider === $('provider').value).map(m => {
    const option = document.createElement('option'); option.value = m.id; option.textContent = m.id; return option;
  }));
}
function resetMetrics() {
  for (const id of ['ttft','speed','input-count','output-count','cost']) $(id).textContent = '—';
  $('total').textContent = 'Total tokens: —'; $('usage-badge').textContent = 'WAITING';
  $('cost-caption').textContent = 'Waiting for usage';
  $('usage-note').textContent = 'Interim usage may be estimated or lag behind the text. Final counts come from the provider.';
}
function renderMetrics(chunk) {
  const t = chunk.telemetry; if (!t) return;
  $('ttft').textContent = t.ttft_ms == null ? '—' : t.ttft_ms.toFixed(1);
  $('speed').textContent = t.tokens_per_second == null ? '—' : t.tokens_per_second.toFixed(1);
  $('input-count').textContent = t.input_tokens ?? '—'; $('output-count').textContent = t.output_tokens ?? '—';
  $('total').textContent = `Total tokens: ${t.total_tokens ?? '—'}`;
  $('cost').textContent = chunk.display_cost_usd == null ? '—' : `$${chunk.display_cost_usd}`;
  $('usage-badge').textContent = chunk.is_final ? 'FINAL' : 'PROVISIONAL';
  $('cost-caption').textContent = chunk.is_final ? 'Calculated from provider usage and configured rates' : 'Provisional · not final billing';
  const sources = {provider:'provider-reported',provider_partial:'partial provider usage',local_estimate:'local tokenizer estimate',unavailable:'not yet available'};
  $('usage-note').textContent = `Usage: ${sources[t.usage_source] ?? 'unknown'}. Cached reads: ${t.cached_input_tokens}; cache writes: ${t.cache_write_input_tokens}.`;
}
function showError(message) { $('error').textContent = message; $('error').hidden = false; }
function setBusy(busy) {
  for (const id of ['send','provider','model','temperature','max-tokens','prompt']) $(id).disabled = busy;
  $('stop').disabled = !busy;
}
$('provider').addEventListener('change',setModels);
$('temperature').addEventListener('input',() => { $('temperature-value').value = $('temperature').value; });
$('stop').addEventListener('click',() => controller?.abort());
$('prompt-form').addEventListener('submit',async event => {
  event.preventDefault(); if (controller) return;
  if (!$('prompt').value.trim()) { showError('Enter a prompt first.'); return; }
  controller = new AbortController(); const activeController = controller;
  setBusy(true); resetMetrics(); $('response').textContent = ''; $('error').hidden = true;
  $('status').textContent = 'Connecting…';
  $('request-detail').textContent = `${$('provider').value} / ${$('model').value}`;
  let finalSeen = false, errorSeen = false;
  try {
    const res = await fetch('/api/stream',{method:'POST',headers:{'Content-Type':'application/json'},signal:activeController.signal,
      body:JSON.stringify({provider:$('provider').value,model:$('model').value,prompt:$('prompt').value,
        temperature:Number($('temperature').value),max_tokens:Number($('max-tokens').value)})});
    if (!res.ok) { const detail = await res.json(); throw new Error(detail.message || 'Request rejected.'); }
    if (!res.body) throw new Error('Streaming is unavailable in this browser.');
    const reader = res.body.getReader(), decoder = new TextDecoder(); let buffer = '';
    try {
      while (true) {
        const {value,done} = await reader.read();
        buffer += decoder.decode(value,{stream:!done});
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0,boundary); buffer = buffer.slice(boundary+2);
          const lines = frame.split('\n');
          const type = lines.find(l => l.startsWith('event: '))?.slice(7);
          const data = lines.filter(l => l.startsWith('data: ')).map(l => l.slice(6)).join('\n');
          if (!data) continue;
          const payload = JSON.parse(data);
          if (type === 'error') { errorSeen = true; showError(`${payload.type}: ${payload.message}`); $('status').textContent = 'Failed · partial results'; }
          if (type === 'chunk') {
            // Never interpret provider text as HTML, Markdown or executable code.
            $('response').textContent += payload.delta_text; renderMetrics(payload);
            if (payload.is_final) {
              finalSeen = true;
              const reason = payload.telemetry?.stop_reason;
              $('status').textContent = ['length','max_tokens'].includes(reason) ? 'Finished · output limit reached' : `Finished${reason ? ' · '+reason : ''}`;
            } else $('status').textContent = 'Streaming…';
          }
        }
        if (done) break;
      }
    } finally { reader.releaseLock(); }
    if (!finalSeen && !errorSeen) throw new Error('Connection ended before final usage. These results are incomplete.');
  } catch (error) {
    if (error.name === 'AbortError') { $('status').textContent = 'Stopped · partial results'; $('usage-badge').textContent = 'INCOMPLETE'; }
    else { showError(error.message || 'Connection failed.'); $('status').textContent = 'Failed · partial results'; }
  } finally {
    if (!finalSeen) { $('usage-badge').textContent = 'INCOMPLETE'; $('cost-caption').textContent = 'Incomplete · actual billing may differ'; }
    if (!$('response').textContent) $('response').textContent = 'No text received.';
    controller = null; setBusy(false);
  }
});
(async () => {
  try { const res = await fetch('/api/models'); if (!res.ok) throw new Error(); models = await res.json(); setModels(); $('send').disabled = false; }
  catch { showError('Could not load models. Restart the local server and refresh.'); }
})();
