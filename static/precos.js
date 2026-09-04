/* REP Campo - painel de preco da concorrencia */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const brl = v => (v || 0).toLocaleString('pt-BR',
  { style: 'currency', currency: 'BRL', minimumFractionDigits: 2 });

const dataBr = iso => {
  if (!iso) return '';
  const d = String(iso).slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : iso;
};

/* Preco velho engana: quem negocia precisa saber se aquilo ainda vale. */
function idade(iso) {
  if (!iso) return { txt: '', classe: '' };
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (dias <= 30) return { txt: `${dias} d`, classe: 'fresco' };
  if (dias <= 90) return { txt: `${dias} d`, classe: 'morno' };
  return { txt: `${dias} d`, classe: 'velho' };
}

let PRIMEIRA = true;

async function carregar() {
  const q = new URLSearchParams({
    concorrente: $('f-concorrente').value, item: $('f-item').value,
    municipio: $('f-municipio').value, desde: $('f-desde').value,
  });
  const r = await fetch('/api/precos?' + q);
  if (!r.ok) {
    $('msg').innerHTML = '<div class="alerta erro">Não consegui carregar os preços.</div>';
    return;
  }
  const d = await r.json();

  if (PRIMEIRA) {
    encher('f-concorrente', d.concorrentes_catalogo, d.opcoes.concorrentes);
    encher('f-item', d.cesta, d.opcoes.itens);
    encher('f-municipio', d.opcoes.municipios, d.opcoes.municipios);
    PRIMEIRA = false;
  }
  desenhar(d.ultimos);
}

/* O filtro mostra tambem o que ainda nao foi pesquisado, marcado - a lacuna e
   informacao: diz onde falta mandar alguem olhar. */
function encher(id, catalogo, comDado) {
  const sel = $(id);
  const tem = new Set(comDado || []);
  const atual = sel.value;
  const primeira = sel.options[0].outerHTML;
  sel.innerHTML = primeira + (catalogo || []).map(x =>
    `<option value="${esc(x)}">${esc(x)}${tem.has(x) ? '' : ' (sem pesquisa)'}</option>`).join('');
  sel.value = atual;
}

function desenhar(linhas) {
  if (!linhas.length) {
    $('tabela-precos').innerHTML =
      '<p class="dica">Nenhum preço coletado com esses filtros. Os preços entram '
      + 'sozinhos quando o representante salva uma ficha do tipo <b>Preço</b>.</p>';
    return;
  }
  const porConcorrente = {};
  linhas.forEach(l => (porConcorrente[l.concorrente] ||= []).push(l));

  $('tabela-precos').innerHTML = Object.entries(porConcorrente)
    .sort((a, b) => a[0].localeCompare(b[0], 'pt-BR'))
    .map(([conc, itens]) => `
      <section class="cartao">
        <h2>${esc(conc)}</h2>
        <div class="rolagem">
        <table class="tabela">
          <thead><tr><th>Item</th><th>R$/m²</th><th>Cidade</th><th>Rota</th>
            <th>Coletado</th><th>Idade</th><th>Condição</th></tr></thead>
          <tbody>${itens.map(l => {
            const i = idade(l.coletado_em);
            return `<tr>
              <td><b>${esc(l.item)}</b></td>
              <td class="num">${esc(brl(l.preco))}</td>
              <td>${esc(l.municipio || '-')}</td>
              <td>${esc(l.rota || '-')}</td>
              <td>${esc(dataBr(l.coletado_em))}</td>
              <td><span class="idade ${i.classe}">${esc(i.txt)}</span></td>
              <td class="dica">${esc(l.condicao_pagamento || '-')}</td>
            </tr>`;
          }).join('')}</tbody>
        </table>
        </div>
      </section>`).join('');
}

/* ------------------------------------------------------------ onde atua */

async function carregarAtuacao() {
  const r = await fetch('/api/precos/onde-atua');
  if (!r.ok) return;
  const d = await r.json();
  if (!d.concorrentes.length) {
    $('lista-atuacao').innerHTML =
      '<p class="dica">Ainda não há pesquisa de preço registrada.</p>';
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

/* --------------------------------------------------------------- abas */

document.querySelectorAll('.aba').forEach(b => b.onclick = () => {
  document.querySelectorAll('.aba').forEach(x => x.classList.remove('ativa'));
  document.querySelectorAll('.tela').forEach(x => x.classList.remove('ativa'));
  b.classList.add('ativa');
  $('tela-' + b.dataset.tela).classList.add('ativa');
  if (b.dataset.tela === 'atuacao') carregarAtuacao();
});

['f-concorrente', 'f-item', 'f-municipio', 'f-desde']
  .forEach(id => $(id).addEventListener('change', carregar));

carregar();
