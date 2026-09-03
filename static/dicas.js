/* Dicas de ajuda. Passa o mouse no desktop, toca no celular.
   Cada dica e um botao com data-dica; o texto aparece numa bolha. */
'use strict';
(function () {
  const esc = t => String(t == null ? '' : t)
    .replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;',
                                 '"': '&quot;', "'": '&#39;' }[c]));

  let bolha = null;

  function caixa() {
    if (!bolha) {
      bolha = document.createElement('div');
      bolha.className = 'bolha-dica oculto';
      bolha.setAttribute('role', 'tooltip');
      document.body.appendChild(bolha);
    }
    return bolha;
  }

  function mostrar(alvo) {
    const texto = alvo.dataset.dica;
    if (!texto) return;
    const b = caixa();
    b.innerHTML = esc(texto);
    b.classList.remove('oculto');

    // posiciona sem sair da tela
    const r = alvo.getBoundingClientRect();
    const largura = Math.min(300, window.innerWidth - 24);
    b.style.maxWidth = largura + 'px';
    const bb = b.getBoundingClientRect();
    let esquerda = r.left + r.width / 2 - bb.width / 2;
    esquerda = Math.max(12, Math.min(esquerda, window.innerWidth - bb.width - 12));
    let topo = r.bottom + 8;
    if (topo + bb.height > window.innerHeight - 8) topo = r.top - bb.height - 8;
    b.style.left = esquerda + 'px';
    b.style.top = Math.max(8, topo) + 'px';
  }

  function esconder() {
    if (bolha) bolha.classList.add('oculto');
  }

  // um clique/toque em qualquer lugar fecha; no botao, alterna
  document.addEventListener('click', ev => {
    const alvo = ev.target.closest('[data-dica]');
    if (!alvo) return esconder();
    // captura: intercepta antes do handler do cartao, senao tocar no "?"
    // tambem escolhia o tipo de visita
    ev.preventDefault();
    ev.stopPropagation();
    const aberta = bolha && !bolha.classList.contains('oculto')
                   && bolha.dataset.de === alvo.dataset.dica;
    if (aberta) return esconder();
    mostrar(alvo);
    bolha.dataset.de = alvo.dataset.dica;
  }, true);

  // no desktop, o mouse basta
  document.addEventListener('mouseover', ev => {
    const alvo = ev.target.closest('[data-dica]');
    if (alvo && window.matchMedia('(hover: hover)').matches) mostrar(alvo);
  });
  document.addEventListener('mouseout', ev => {
    if (ev.target.closest('[data-dica]')
        && window.matchMedia('(hover: hover)').matches) esconder();
  });
  window.addEventListener('scroll', esconder, { passive: true });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') esconder(); });
})();
