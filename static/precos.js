/* REP Campo - comparacao de preco da concorrencia */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const brl = v => (v || 0).toLocaleString('pt-BR',
  { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const dataBr = iso => {
  if (!iso) return '';
  const d = String(iso).slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : iso;
};

/* Preco velho engana quem negocia: a cor diz se aquilo ainda vale. */
function idade(iso) {
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (dias <= 30) return { dias, classe: 'fresco' };
  if (dias <= 90) return { dias, classe: 'morno' };
  return { dias, classe: 'velho' };
}

let PRIMEIRA = true;

async function carregar() {
  const q = new URLSearchParams({
    rota: $('f-rota').value, municipio: $('f-municipio').value,
    cliente: $('f-cliente').value, desde: $('f-desde').value,
  });
  const r = await fetch('/api/precos/matriz?' + q);
  if (!r.ok) {
    $('msg').innerHTML = '<div class="alerta erro">Não consegui carregar os preços.</div>';
    return;
  }
  const d = await r.json();
  if (PRIMEIRA) { encherFiltros(d.recortes); PRIMEIRA = false; }
  desenhar(d);
}

function encherFiltros(rec) {
  const opc = (sel, itens, valor, texto) => {
    const e = $(sel), primeira = e.options[0].outerHTML;
    e.innerHTML = primeira + itens.map(x =>
      `<option value="${esc(valor(x))}">${esc(texto(x))}</option>`).join('');
  };
  opc('f-rota', rec.rotas, x => x, x => x);
  opc('f-municipio', rec.municipios, x => x, x => x);
  opc('f-cliente', rec.clientes, x => x.codigo, x => x.nome || x.codigo);
}

function desenhar(d) {
  const alvo = $('grade-precos');
  if (!d.concorrentes.length) {
    alvo.innerHTML = '<p class="dica">Nenhum preço pesquisado neste recorte. '
      + 'Os preços entram sozinhos quando o representante salva uma ficha do tipo '
      + '<b>Preço</b>.</p>';
    $('resumo-grade').textContent = '';
    return;
  }
  $('resumo-grade').innerHTML =
    `<b>${d.concorrentes.length}</b> concorrente(s) &middot; `
    + `<b>${d.coletas}</b> preço(s) neste recorte`;

  const cab = d.concorrentes.map(c => `<th>${esc(c)}</th>`).join('');

  const corpo = d.grupos.map(g => {
    const linhas = g.itens.map(it => {
      const celulas = d.concorrentes.map(c => {
        const v = it.precos[c];
        if (!v) return '<td class="vazia">—</td>';
        const i = idade(v.coletado_em);
        const dica = `${dataBr(v.coletado_em)} · ${v.municipio || 'sem cidade'}`
          + ` · ${i.dias} dias · por ${v.por}`;
        return `<td class="celula ${i.classe}" title="${esc(dica)}">
          <b>${esc(brl(v.preco))}</b><small>${i.dias} d</small></td>`;
      }).join('');
      return `<tr><th class="item">${esc(it.item)}</th>${celulas}</tr>`;
    }).join('');
    return `<tr class="grupo"><th colspan="${d.concorrentes.length + 1}">${esc(g.grupo)}</th></tr>${linhas}`;
  }).join('');

  alvo.innerHTML = `<div class="rolagem"><table class="grade">
    <thead><tr><th class="item">Item</th>${cab}</tr></thead>
    <tbody>${corpo}</tbody></table></div>`;
}

/* ------------------------------------------------------------ onde atua */

async function carregarAtuacao() {
  const r = await fetch('/api/precos/onde-atua');
  if (!r.ok) return;
  const d = await r.json();
  if (!d.concorrentes.length) {
    $('lista-atuacao').innerHTML = '<p class="dica">Ainda não há pesquisa de preço registrada.</p>';
    return;
  }
  $('lista-atuacao').innerHTML = d.concorrentes.map(c => `
    <section class="cartao">
      <h2>${esc(c.concorrente)} <span class="dica">${c.coletas} coleta(s)</span></h2>
      <div class="chips">${c.lugares.map(l =>
        `<span class="chip-lugar">${esc(l.municipio)}
          <small>${esc(l.rota)} · visto em ${esc(dataBr(l.visto_em))}</small></span>`).join('')}
      </div>
    </section>`).join('');
}

/* --------------------------------------------------------------- telas */

document.querySelectorAll('.aba').forEach(b => b.onclick = () => {
  document.querySelectorAll('.aba').forEach(x => x.classList.remove('ativa'));
  document.querySelectorAll('.tela').forEach(x => x.classList.remove('ativa'));
  b.classList.add('ativa');
  $('tela-' + b.dataset.tela).classList.add('ativa');
  if (b.dataset.tela === 'atuacao') carregarAtuacao();
});

['f-rota', 'f-municipio', 'f-cliente', 'f-desde']
  .forEach(id => $(id).addEventListener('change', carregar));

$('btn-limpar').onclick = () => {
  ['f-rota', 'f-municipio', 'f-cliente', 'f-desde'].forEach(id => ($(id).value = ''));
  carregar();
};

carregar();
