window.pageImport = () => {
  const form = document.querySelector('#import-form');
  form.onsubmit = async event => {
    event.preventDefault();
    const file = document.querySelector('#import-file').files[0];
    if (!file) return;
    const button = form.querySelector('button');
    const message = document.querySelector('#import-message');
    try {
      button.disabled = true;
      button.textContent = 'Doğrulanıyor…';
      const response = await fetch('/api/imports/processes', { method: 'POST', body: new FormData(form) });
      const payload = await response.json();
      if (!response.ok) throw Error(payload.detail || 'İçe aktarma tamamlanamadı.');
      const r = payload.report;
      message.textContent = payload.message;
      const report = document.querySelector('#import-report');
      report.hidden = false;
      report.innerHTML = `<p class="eyebrow">İÇE AKTARMA SONUCU</p><h2>${payload.filename}</h2><p>Kaynak: <strong>${r.source_rows}</strong> · Aktarılan: <strong>${r.imported_rows}</strong> · Reddedilen: <strong>${r.rejected_rows}</strong> · Tekrar: <strong>${r.duplicate_rows}</strong></p>`;
      toast('Dosya yerel veritabanına aktarıldı.');
    } catch (error) {
      message.textContent = error.message;
      toast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = 'Doğrula ve içe aktar';
    }
  };
};
