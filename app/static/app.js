const api = async (url, options = {}) => {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const body = await response.json();
  if (!response.ok) throw Error(body.detail || 'İşlem tamamlanamadı.');
  return body;
};

const safe = value => String(value ?? '—').replace(/[&<>'"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[char]));

const toast = message => {
  const element = document.querySelector('#toast');
  element.textContent = message;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 3000);
};

const badge = (level, score) => {
  const className = level === 'Yüksek' ? 'high' : level === 'Orta' ? 'medium' : 'low';
  return `<span class="badge risk-${className}">${score ?? '—'} · ${level ?? 'Tahmin yok'}</span>`;
};

window.pageDashboard = async () => {
  // Güncel Dashboard metrikleri Jinja2 tarafından sunucuda çiziliyor. Eski
  // dinamik elemanlar varsa yalnızca o durumda API ile yenileme yapılır.
  if (document.querySelector('#total-open')) try {
    const [dashboard, processes] = await Promise.all([
      api('/api/dashboard'), api('/api/processes?limit=8'),
    ]);
    const metrics = {
      'total-open': dashboard.total_open_processes,
      'predicted-open': dashboard.predicted_open_processes,
      'high-risk': dashboard.high_risk_processes,
      'average-risk': dashboard.average_risk_score ?? '—',
    };
    Object.entries(metrics).forEach(([id, value]) => { document.querySelector(`#${id}`).textContent = value; });
    document.querySelector('#risk-table').innerHTML = processes.items.map(item => `<tr>
      <td><a href="/processes/${item.id}">${safe(item.external_id)}</a></td>
      <td>${safe(item.current_stage)}</td><td>${safe(item.deadline)}</td>
      <td>${badge(item.risk_level, item.risk_score)}</td></tr>`).join('')
      || '<tr><td colspan="4" class="empty">Kayıt bulunamadı.</td></tr>';
    document.querySelector('#type-distribution').innerHTML = dashboard.process_type_distribution.map(item =>
      `<div><span>${safe(item.process_type)}</span><strong>${item.count}</strong></div>`
    ).join('');
  } catch (error) { toast(error.message); }

  const batchButton = document.querySelector('#batch-predict');
  if (batchButton) batchButton.onclick = async event => {
    const button = event.currentTarget;
    const progress = document.querySelector('#batch-progress');
    const cancelButton = document.querySelector('#batch-cancel');
    try {
      button.disabled = true;
      button.textContent = 'İşlem başlatılıyor…';
      const job = await api('/api/predictions/batch/start', { method: 'POST', body: JSON.stringify({ limit: 10000 }) });
      cancelButton.hidden = false;
      cancelButton.disabled = false;
      cancelButton.onclick = async () => {
        cancelButton.disabled = true;
        cancelButton.textContent = 'Durduruluyor…';
        await api(`/api/predictions/batch/${job.job_id}/cancel`, { method: 'POST' });
      };
      const poll = async () => {
        const status = await api(`/api/predictions/batch/${job.job_id}/status`);
        progress.textContent = status.total
          ? `${status.processed.toLocaleString('tr-TR')} / ${status.total.toLocaleString('tr-TR')} iş değerlendirildi (%${status.percent})`
          : 'Açık işler hazırlanıyor…';
        if (status.status === 'completed') {
          toast(`${status.processed.toLocaleString('tr-TR')} açık iş değerlendirildi.`);
          window.location.assign('/processes');
          return;
        }
        if (status.status === 'cancelled') {
          progress.textContent = `İşlem durduruldu. ${status.processed.toLocaleString('tr-TR')} iş güncellendi.`;
          button.disabled = false;
          button.textContent = 'Açık işleri değerlendir';
          cancelButton.hidden = true;
          toast('Toplu tahmin işlemi durduruldu.');
          return;
        }
        if (status.status === 'failed') {
          throw Error('Toplu tahmin işlemi tamamlanamadı.');
        }
        window.setTimeout(poll, 700);
      };
      await poll();
    } catch (error) {
      toast(error.message);
      button.disabled = false;
      button.textContent = 'Açık işleri değerlendir';
      cancelButton.hidden = true;
    }
  };
};

window.pageProcesses = async () => {
  const draw = rows => {
    document.querySelector('#process-count').textContent = `${rows.length} kayıt`;
    document.querySelector('#process-table').innerHTML = rows.map(item => `<tr>
      <td>${safe(item.external_id)}</td><td>${safe(item.process_type)}</td><td>${safe(item.current_stage)}</td>
      <td>${safe(item.responsible_team)}</td><td>${safe(item.deadline)}</td>
      <td>${badge(item.risk_level, item.risk_score)}</td><td><a href="/processes/${item.id}">İncele</a></td></tr>`).join('')
      || '<tr><td colspan="7" class="empty">Kayıt bulunamadı.</td></tr>';
  };
  const load = async () => {
    try {
      const risk = document.querySelector('#risk-filter').value;
      const data = await api(`/api/processes?limit=1000${risk ? `&risk_level=${encodeURIComponent(risk)}` : ''}`);
      draw(data.items);
    } catch (error) { toast(error.message); }
  };
  document.querySelector('#risk-filter').onchange = load;
  document.querySelector('#refresh-processes').onclick = load;
  await load();
};

window.pageProcessDetail = async () => {
  const root = document.querySelector('#process-detail');
  const processId = root.dataset.processId;
  let latestPrediction = null;
  let deadlineContext = null;
  let predictionHistory = [];
  const renderPredictionHistory = () => {
    const element = document.querySelector('#prediction-history');
    element.innerHTML = predictionHistory.map(item => `<tr>
      <td>${safe(String(item.predicted_at || '').replace('T', ' ').slice(0, 16))}</td>
      <td>${safe(item.model_version)}</td><td>${badge(item.risk_level, item.risk_score)}</td>
      <td>${safe(item.predicted_remaining_days)} gün</td></tr>`).join('')
      || '<tr><td colspan="4" class="empty">Henüz tahmin geçmişi yok.</td></tr>';
  };
  const showDeadlineContext = context => {
    const element = document.querySelector('#deadline-alert');
    if (context.status === 'overdue') {
      element.innerHTML = `<strong>Gecikmiş — ${context.days} gün.</strong> Bu kesin bir takvim durumudur; model riski artık erken uyarı olarak yorumlanmamalıdır.`;
    } else if (context.status === 'urgent') {
      element.innerHTML = `<strong>Acil — son tarihe ${context.days} gün kaldı.</strong> Model riski düşük/orta olsa bile operasyonel olarak önceliklidir.`;
    } else {
      element.textContent = `Plan dahilinde — son tarihe ${context.days} gün kaldı.`;
    }
  };
  const showPrediction = prediction => {
    if (!prediction) return;
    latestPrediction = { ...prediction, prediction_id: prediction.prediction_id ?? prediction.id };
    document.querySelector('#prediction-result').innerHTML = `<div class="score">${prediction.risk_score}/100</div>${badge(prediction.risk_level, prediction.risk_score)}<p>Tahmini kalan süre: <strong>${prediction.predicted_remaining_days} gün</strong></p>`;
    const uncertainty = prediction.remaining_days_uncertainty;
    if (uncertainty) {
      document.querySelector('#prediction-result').insertAdjacentHTML(
        'beforeend', `<p class="uncertainty">Yaklaşık hata payı: ±${safe(uncertainty.mae_days)} gün · Beklenen aralık: ${safe(uncertainty.lower_days)}–${safe(uncertainty.upper_days)} gün</p>`,
      );
    }
    const factors = prediction.explanation?.top_risk_factors || [];
    const contextNote = prediction.explanation?.context_note;
    document.querySelector('#risk-factors').innerHTML = factors.map(factor =>
      `<div><strong>${safe(factor.label)}</strong><span>${factor.risk_impact_points} puanlık model etkisi</span></div>`
    ).join('') || '<p class="empty">Belirgin faktör bulunamadı.</p>';
    if (contextNote) {
      document.querySelector('#risk-factors').insertAdjacentHTML(
        'afterbegin', `<p class="empty"><strong>Takvim bağlamı:</strong> ${safe(contextNote)}</p>`,
      );
    }
    const actions = prediction.explanation?.recommended_actions || [];
    const actionElement = document.querySelector('#recommended-actions');
    actionElement.innerHTML = actions.map(action =>
      `<div><strong>${safe(action.title)}</strong><span class="action-note">${safe(action.reason)}</span></div>`
    ).join('') || '<p class="empty">Bu kayıt için belirgin bir aksiyon önerisi oluşmadı.</p>';
  };
  try {
    const data = await api(`/api/processes/${processId}`);
    const process = data.process;
    deadlineContext = data.deadline_context;
    showDeadlineContext(deadlineContext);
    document.querySelector('#detail-name').textContent = `${process.external_id} · ${process.process_type}`;
    const labels = { current_stage: 'Mevcut aşama', responsible_team: 'Ekip', priority: 'Öncelik', deadline: 'Son tarih', revision_count: 'Revizyon', missing_document_count: 'Eksik belge', days_in_current_stage: 'Aşamada gün', team_workload: 'Ekip iş yükü' };
    document.querySelector('#process-fields').innerHTML = Object.entries(labels).map(([key, label]) => `<div><dt>${label}</dt><dd>${safe(process[key])}</dd></div>`).join('');
    ['missing_document_count', 'revision_count', 'days_in_current_stage'].forEach(key => { document.querySelector(`[name="${key}"]`).value = process[key]; });
    const history = data.prediction_history[0];
    predictionHistory = data.prediction_history;
    renderPredictionHistory();
    if (history) {
      showPrediction({ ...history, explanation: history.explanation });
      document.querySelector('#run-prediction').textContent = 'Tahmini güncelle';
      document.querySelector('#prediction-note').textContent = `Son kayıt: ${String(history.predicted_at).replace('T', ' ').slice(0, 16)}. Süreç verisi değişmediyse aynı gün yeniden çalıştırmaya gerek yok.`;
    }
  } catch (error) { toast(error.message); }
  document.querySelector('#run-prediction').onclick = async () => {
    try {
      const prediction = await api(`/api/predictions/${processId}/run`, { method: 'POST' });
      showPrediction(prediction);
      if (!prediction.reused_existing_prediction) {
        predictionHistory.unshift({ ...prediction, id: prediction.prediction_id, predicted_at: new Date().toISOString() });
        renderPredictionHistory();
        document.querySelector('#run-prediction').textContent = 'Tahmini güncelle';
        toast('Yeni tahmin kaydedildi.');
      } else {
        toast('Bugünkü tahmin zaten kaydedilmişti.');
      }
    }
    catch (error) { toast(error.message); }
  };
  document.querySelector('#simulation-form').onsubmit = async event => {
    event.preventDefault();
    if (!latestPrediction) { toast('Önce mevcut tahmini üret.'); return; }
    if (deadlineContext?.status === 'overdue') {
      document.querySelector('#simulation-result').innerHTML = '<p class="empty"><strong>Bu iş zaten gecikmiş.</strong> Sistem, zamanında bitme için erken uyarı tahmini yapar; son tarih geçtikten sonra bu karşı-senaryo anlamlı bir erken uyarı sonucu vermez.</p>';
      return;
    }
    const overrides = {};
    new FormData(event.currentTarget).forEach((value, key) => { overrides[key] = Number(value); });
    try {
      const result = await api('/api/simulate', { method: 'POST', body: JSON.stringify({ process_id: Number(processId), overrides }) });
      // Aynı gün hesaplanan baz tahminle karşılaştırır; eski kayıtla değil.
      const difference = result.simulation.risk_score - result.baseline.risk_score;
      const change = difference === 0 ? 'değişmedi' : difference < 0 ? `${Math.abs(difference)} puan düştü` : `${difference} puan yükseldi`;
      document.querySelector('#simulation-result').innerHTML = `Bugünkü baz tahmin: ${badge(result.baseline.risk_level, result.baseline.risk_score)} · Yeni senaryo: ${badge(result.simulation.risk_level, result.simulation.risk_score)} · Risk ${change} · Tahmini kalan süre ${result.simulation.predicted_remaining_days} gün`;
      if (difference === 0 && result.simulation.delay_probability < result.baseline.delay_probability) {
        const before = (result.baseline.delay_probability * 100).toFixed(2).replace('.', ',');
        const after = (result.simulation.delay_probability * 100).toFixed(2).replace('.', ',');
        document.querySelector('#simulation-result').insertAdjacentHTML(
          'beforeend', `<br><small>Ham gecikme olasılığı %${before} → %${after} düştü; fakat 0–100 puanı yuvarlandığı için görünür skor aynı kaldı.</small>`,
        );
      }
    } catch (error) { toast(error.message); }
  };
  document.querySelector('#feedback-form').onsubmit = async event => {
    event.preventDefault();
    if (!latestPrediction?.prediction_id) { toast('Önce tahmin üret.'); return; }
    const form = new FormData(event.currentTarget);
    const actualOutcome = form.get('actual_outcome');
    const payload = {
      prediction_id: latestPrediction.prediction_id,
      feedback_type: form.get('feedback_type'),
      comment: form.get('comment') || null,
      actual_outcome: actualOutcome === '' ? null : Number(actualOutcome),
    };
    try {
      await api('/api/feedback', { method: 'POST', body: JSON.stringify(payload) });
      document.querySelector('#feedback-result').textContent = 'Geri bildirim yerel olarak kaydedildi. Bu kayıt sonraki model değerlendirmesinde kullanılabilir.';
      toast('Geri bildirim kaydedildi.');
    } catch (error) { toast(error.message); }
  };
};

window.pageModels = async () => {
  try {
    const [data, monitoring, drift] = await Promise.all([api('/api/models/active'), api('/api/models/monitoring'), api('/api/models/data-drift')]);
    document.querySelector('#models-grid').innerHTML = data.items.map(item => {
      const metric = item.model_type === 'classification' ? 'roc_auc' : 'mae';
      const extraMetrics = Object.entries(item.metrics).filter(([key]) => key !== metric && key !== 'confusion_matrix').map(([key, value]) => `${safe(key.toUpperCase())}: ${safe(value)}`).join(' · ');
      return `<article class="model-card"><p class="eyebrow">${safe(item.model_type)}</p><h3>${safe(item.model_version)}</h3><div>${metric.toUpperCase()}: <strong>${item.metrics[metric] ?? '—'}</strong></div><p class="empty">${extraMetrics || 'Ek metrik kaydı yok'}</p><p class="empty">${item.feature_list.length} özellik · ${safe(item.trained_at.slice(0, 10))}</p></article>`;
    }).join('');
    const classifier = data.items.find(item => item.model_type === 'classification');
    const matrix = classifier?.metrics?.confusion_matrix;
    document.querySelector('#confusion-matrix').innerHTML = Array.isArray(matrix) && matrix.length === 2 ? `<table>
      <thead><tr><th></th><th>Model: gecikmez</th><th>Model: gecikir</th></tr></thead>
      <tbody><tr><th>Gerçek: gecikmez</th><td>${safe(matrix[0][0])} doğru negatif</td><td>${safe(matrix[0][1])} yanlış alarm</td></tr>
      <tr><th>Gerçek: gecikir</th><td>${safe(matrix[1][0])} kaçırılan gecikme</td><td>${safe(matrix[1][1])} doğru pozitif</td></tr></tbody></table>`
      : '<p class="empty">Aktif sınıflandırma modeli için confusion matrix bulunamadı.</p>';
    document.querySelector('#monitoring-grid').innerHTML = [
      ['Toplam geri bildirim', monitoring.total_feedback],
      ['Gerçek sonucu bilinen', monitoring.known_outcomes],
      ['Gecikerek tamamlanan', monitoring.delayed_outcomes],
      ['Hatalı görünen tahmin', monitoring.by_type.incorrect || 0],
    ].map(([label, value]) => `<article><span>${safe(label)}</span><strong>${safe(value)}</strong></article>`).join('');
    const field = monitoring.field_performance;
    document.querySelector('#field-performance').innerHTML = field.sample_size ? [
      ['Örnek sayısı', field.sample_size], ['Accuracy', field.accuracy], ['Precision', field.precision],
      ['Recall', field.recall], ['F1', field.f1],
      ['Confusion matrix', `[[${field.confusion_matrix[0].join(', ')}], [${field.confusion_matrix[1].join(', ')}]]`],
    ].map(([label, value]) => `<div><span>${safe(label)}</span><strong>${safe(value)}</strong></div>`).join('')
      : '<p class="empty">Henüz gerçek sonucu girilmiş tahmin yok. İş tamamlandığında iş detayındaki geri bildirim alanından sonucu kaydet.</p>';
    const label = { normal: 'Normal', izle: 'İzlenmeli', yüksek: 'Yüksek değişim' };
    document.querySelector('#drift-report').innerHTML = `<div><strong>Genel durum</strong><span>${safe(label[drift.severity])} · eğitim bağlamı ${safe(drift.reference_count)} kayıt, açık işler ${safe(drift.current_count)} kayıt</span></div>`
      + drift.fields.slice(0, 5).map(item => `<div><span>${safe(item.field)} · ${safe(item.method)}</span><strong>${safe(item.score)} · ${safe(label[item.level])}</strong></div>`).join('')
      + `<p class="empty">${safe(drift.note)}</p>`;
  } catch (error) { toast(error.message); }
};

window.pageQuality = async () => {
  try {
    const data = await api('/api/data-quality');
    [['source-rows', 'source_rows'], ['valid-rows', 'valid_rows'], ['rejected-rows', 'rejected_rows'], ['duplicate-rows', 'duplicate_rows']].forEach(([id, key]) => { document.querySelector(`#${id}`).textContent = data[key]; });
    const renderList = values => Object.entries(values).map(([key, value]) => `<div><span>${safe(key)}</span><strong>${value}</strong></div>`).join('');
    document.querySelector('#missing-values').innerHTML = renderList(data.missing_values);
    document.querySelector('#outliers').innerHTML = renderList(data.iqr_outlier_counts);
    const rejectionPanel = document.querySelector('#rejection-reasons');
    if (data.rejected_rows === 0) {
      rejectionPanel.innerHTML = '<p class="empty">Bu veri yüklemesinde reddedilen kayıt yok. Yeni bir CSV/XLSX içe aktarıldığında tarih, eksik alan, sayı, durum ve tekrar kimliği hataları burada özetlenir.</p>';
    } else {
      rejectionPanel.innerHTML = renderList(data.rejection_reason_counts || {})
        || '<p class="empty">Bu eski raporda red nedenlerinin ayrıntısı bulunmuyor.</p>';
    }
  } catch (error) { toast(error.message); }
};

window.pageSystemHealth = async () => {
  const statusLabel = { healthy: 'Sağlıklı', warning: 'İzlenmeli', critical: 'Kritik', unavailable: 'Kullanılamıyor' };
  const statusBadge = status => `<span class="badge risk-${status === 'critical' ? 'high' : status === 'warning' ? 'medium' : 'low'}">${safe(statusLabel[status] || status)}</span>`;
  const localTime = value => {
    if (!value) return '—';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? safe(value) : parsed.toLocaleString('tr-TR');
  };
  const render = data => {
    const latest = data.latest;
    const snapshot = latest.snapshot || latest;
    document.querySelector('#health-status').innerHTML = `${statusBadge(snapshot.status)} ${safe(snapshot.alert_summary || 'Kritik eşik aşılmadı.')} · Son ölçüm: ${localTime(snapshot.measured_at || latest.created_at)}`;
    const metrics = [
      ['CPU', snapshot.cpu?.percent, `%${snapshot.cpu?.percent ?? '—'}`, `${snapshot.cpu?.core_count ?? '—'} mantıksal çekirdek`],
      ['RAM', snapshot.memory?.percent, `%${snapshot.memory?.percent ?? '—'}`, `${snapshot.memory?.used_gb ?? '—'} / ${snapshot.memory?.total_gb ?? '—'} GB`],
      ['C: depolama doluluğu', snapshot.disk?.percent, `%${snapshot.disk?.percent ?? '—'}`, `${snapshot.disk?.used_gb ?? '—'} / ${snapshot.disk?.total_gb ?? '—'} GB`],
      ['NVIDIA GPU', snapshot.gpu?.percent, snapshot.gpu?.available ? `%${snapshot.gpu.percent}` : 'Veri yok', snapshot.gpu?.available ? safe(snapshot.gpu.name) : 'NVIDIA GPU algılanmadı'],
    ];
    document.querySelector('#health-metrics').innerHTML = metrics.map(([label, value, display, note]) => `<article class="${Number(value) >= 90 ? 'alert' : ''}"><span>${safe(label)}</span><strong>${safe(display)}</strong><small>${note}</small></article>`).join('');
    document.querySelector('#health-history').innerHTML = data.history.map(event => `<tr><td>${localTime(event.snapshot?.measured_at || event.created_at)}</td><td>${statusBadge(event.status)}</td><td>%${safe(event.cpu_percent)}</td><td>%${safe(event.memory_percent)}</td><td>%${safe(event.disk_percent)}</td><td>${safe(event.alert_summary || '—')}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">Henüz ölçüm kaydı yok.</td></tr>';
  };
  const load = async () => {
    try { render(await api('/api/system-health')); } catch (error) { toast(error.message); }
  };
  document.querySelector('#health-check').onclick = async event => {
    const button = event.currentTarget;
    try {
      button.disabled = true;
      button.textContent = 'Ölçülüyor…';
      await api('/api/system-health/check', { method: 'POST' });
      await load();
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = 'Şimdi kontrol et'; }
  };
  await load();
};
