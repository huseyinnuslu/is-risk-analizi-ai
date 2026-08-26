window.pageProcesses = async () => {
  const escapeHtml = value => String(value ?? '—').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  const calendarBadge = item => {
    if (item.deadline_status === 'overdue') return `<span class="badge risk-high">Gecikmiş · ${Math.abs(item.deadline_days_remaining)} gün</span>`;
    if (item.deadline_status === 'urgent') return `<span class="badge risk-medium">Acil · ${item.deadline_days_remaining} gün</span>`;
    return `<span class="badge risk-low">Plan dahilinde · ${item.deadline_days_remaining} gün</span>`;
  };
  const riskBadge = item => {
    const tone = item.risk_level === 'Yüksek' ? 'high' : item.risk_level === 'Orta' ? 'medium' : 'low';
    return `<span class="badge risk-${tone}">${item.risk_score ?? '—'} · ${item.risk_level ?? 'Tahmin yok'}</span>`;
  };
  const load = async () => {
    try {
      const risk = document.querySelector('#risk-filter').value;
      const deadline = document.querySelector('#deadline-filter').value;
      const params = new URLSearchParams({ limit: '1000' });
      if (risk) params.set('risk_level', risk);
      if (deadline) params.set('deadline_status', deadline);
      const response = await fetch(`/api/processes?${params}`);
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || 'Liste yüklenemedi.');
      document.querySelector('#process-count').textContent = `${data.items.length} kayıt`;
      document.querySelector('#process-table').innerHTML = data.items.map(item => `<tr><td>${escapeHtml(item.external_id)}</td><td>${escapeHtml(item.process_type)}</td><td>${escapeHtml(item.current_stage)}</td><td>${escapeHtml(item.responsible_team)}</td><td>${escapeHtml(item.deadline)}</td><td>${calendarBadge(item)}</td><td>${riskBadge(item)}</td><td><a href="/processes/${item.id}">İncele</a></td></tr>`).join('') || '<tr><td colspan="8" class="empty">Bu filtrelerle kayıt bulunamadı.</td></tr>';
    } catch (error) { toast(error.message); }
  };
  document.querySelector('#deadline-filter').onchange = load;
  document.querySelector('#risk-filter').onchange = load;
  document.querySelector('#refresh-processes').onclick = load;
  await load();
};
