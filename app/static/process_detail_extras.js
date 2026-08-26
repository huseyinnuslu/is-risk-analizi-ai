(() => {
  const basePage = window.pageProcessDetail;
  const escapeHtml = value => String(value ?? '—').replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
  window.pageProcessDetail = async () => {
    await basePage();
    document.querySelectorAll('#process-fields div').forEach(item => {
      const label = item.querySelector('dt');
      const value = item.querySelector('dd');
      if (label?.textContent.trim() === 'Ekip iş yükü' && value) {
        label.textContent = 'Ekip kapasite kullanımı';
        value.textContent = `${value.textContent}%`;
      }
    });
    document.querySelectorAll('#risk-factors span').forEach(element => {
      const value = element.textContent.match(/[0-9]+(?:\.[0-9]+)?/)?.[0];
      if (value) element.textContent = `Risk olasılığı etkisi: ${value} yüzde puan`;
    });
    const processId = document.querySelector('#process-detail').dataset.processId;
    const response = await fetch(`/api/processes/${processId}`);
    if (!response.ok) return;
    const rows = (await response.json()).similar_completed_processes || [];
    document.querySelector('#similar-processes').innerHTML = rows.map(row => `<tr>
      <td>${escapeHtml(row.external_id)}</td><td>${escapeHtml(row.current_stage)}</td>
      <td>${escapeHtml(row.responsible_team)}</td><td>${escapeHtml(row.completed_at)}</td>
      <td>${escapeHtml(row.total_duration_days)} gün</td>
      <td>${row.is_delayed ? `Gecikti — ${row.deadline_difference_days} gün` : `Zamanında — ${Math.abs(row.deadline_difference_days)} gün erken`}</td></tr>`).join('')
      || '<tr><td colspan="6" class="empty">Bu ölçütlerle eşleşen geçmiş iş bulunamadı.</td></tr>';
  };
})();
