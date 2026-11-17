/* Shared header, footer and small helpers */
(function () {
  const page = document.body.dataset.page || '';
  const nav = [
    ['index.html', 'Home', 'home'],
    ['guide.html', 'Step-by-step guide', 'guide'],
    ['finder.html', 'Roots Finder', 'finder'],
    ['about.html', 'About HJ', 'about'],
    ['about.html#donate', 'Donate', 'donate']
  ];
  const hdr = document.getElementById('hdr');
  if (hdr) {
    hdr.className = 'top';
    hdr.innerHTML = `<div class="bar">
      <a class="brand" href="index.html">Korean Roots <span>Finder</span></a>
      <nav class="main">${nav.map(([h, l, k]) =>
        `<a href="${h}" class="${k === page ? 'on' : ''} ${k === 'donate' ? 'donate' : ''}">${l}</a>`).join('')}</nav>
    </div>`;
  }
  const ft = document.getElementById('ftr');
  if (ft) {
    ft.className = 'foot';
    ft.innerHTML = `<div class="in">
      <div>
        <h4>Korean Roots Finder</h4>
        <p>A free, volunteer-run guide for Korean adoptees beginning a birth-family search. Made in Seoul by <a href="about.html">HJ Kim</a>.</p>
        <p>Independent. Not affiliated with NCRC, the Korean police, any adoption agency or any government body.</p>
      </div>
      <div>
        <h4>Start here</h4>
        <a href="guide.html">Step-by-step guide</a><br>
        <a href="finder.html">Roots Finder</a><br>
        <a href="https://www.kadoption.or.kr/home/eng/main.do" target="_blank" rel="noopener">NCRC adoptee portal (official)</a><br>
        <a href="https://goal.or.kr/" target="_blank" rel="noopener">G.O.A.'L</a>
      </div>
      <div>
        <h4>Support this work</h4>
        <a href="about.html">About HJ Kim</a><br>
        <a href="about.html#donate">Donate (PayPal / crypto)</a><br>
        <a href="https://forms.gle/z9WPkE3ZgyWG4sxg8" target="_blank" rel="noopener">Contact form</a><br>
        <a href="https://www.index.go.kr/unity/potal/main/EachDtlPageDetail.do?idx_cd=2708" target="_blank" rel="noopener">Official adoption statistics</a>
      </div>
    </div>
    <div class="fine">Nothing on this site is legal advice. Links were checked in 2026; verify details with each organisation. Never pay a fee for something NCRC or the Korean police do for free.</div>`;
  }
  const t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t);
  let tm;
  window.toast = (msg) => { t.textContent = msg; t.classList.add('show'); clearTimeout(tm); tm = setTimeout(() => t.classList.remove('show'), 1800); };
  window.copyText = async (txt, msg) => {
    try { await navigator.clipboard.writeText(txt); }
    catch (e) { const a = document.createElement('textarea'); a.value = txt; document.body.appendChild(a); a.select(); document.execCommand('copy'); a.remove(); }
    window.toast(msg || 'Copied');
  };
  window.esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
})();
