/* REP Campo - painel do gestor */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const brl = v => (v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const dataBR = iso => { if (!iso) return '—'; const d = new Date(iso); return isNaN(d) ? '—' : d.toLocaleDateString('pt-BR'); };

let COBERTURA = [];

/* ------------------------------------------------------------------ abas */
document.querySelectorAll('.aba').forEach(b => b.onclick = () => {
  document.querySelectorAll('.aba').forEach(x => x.classList.remove('ativa'));
  document.querySelectorAll('.tela').forEach(x => x.classList.remove('ativa'));
  b.classList.add('ativa');
  $('tela-' + b.dataset.tela).classList.add('ativa');
  if (b.dataset.tela === 'fichas') carregarFichas();
});

/* ------------------------------------------------------------- cobertura */
async function carregarCobertura() {
  const curvas = $('c-curvas').value;
  const r = await fetch('/api/gestor/cobertura?curvas=' + encodeURIComponent(curvas));
  if (!r.ok) return;
  const d = await r.json();
  COBERTURA = d.clientes;

  $('cartoes-cob').innerHTML = `
    <div class="cartao"><div class="num">${d.cobertura_pct}%</div>
      <div class="rot">cobertura no ciclo</div></div>
    <div class="cartao"><div class="num ${d.vencidos ? 'num-alerta' : ''}">${d.vencidos}</div>
      <div class="rot">clientes vencidos</div></div>
    <div class="cartao"><div class="num ${d.nunca_visitados ? 'num-alerta' : ''}">${d.nunca_visitados}</div>
      <div class="rot">nunca visitados</div></div>
    <div class="cartao"><div class="num">${brl(d.risco_reais)}</div>
      <div class="rot">faturamento 12m sem cobertura</div></div>
    <div class="cartao"><div class="num">${d.total}</div>
      <div class="rot">clientes na seleção</div></div>`;

  const muns = [...new Set(COBERTURA.map(c => c.cidade).filter(Boolean))].sort();
  $('c-lista-mun').innerHTML = muns.map(m => `<option value="${esc(m)}">`).join('');
  desenharCobertura();
}

function filtrarCobertura() {
  const modo = $('c-filtro').value;
  const mun = ($('c-municipio').value || '').toLowerCase().trim();
  return COBERTURA.filter(c => {
    if (modo === 'vencidos' && !c.vencido) return false;
    if (modo === 'nunca' && c.dias !== null) return false;
    if (mun && !(c.cidade || '').toLowerCase().includes(mun)) return false;
    return true;
  });
}

function desenharCobertura() {
  const linhas = filtrarCobertura();
  const tb = document.querySelector('#tab-cobertura tbody');
  $('cob-vazio').classList.toggle('oculto', linhas.length > 0);
  tb.innerHTML = linhas.slice(0, 400).map(c => {
    const nunca = c.dias === null;
    const cls = nunca ? 'nunca' : (c.vencido ? 'vencido' : '');
    const dias = nunca
      ? '<span class="dias-nunca">nunca</span>'
      : `<span class="${c.vencido ? 'dias-mal' : ''}">${c.dias}</span>`;
    return `<tr class="${cls}">
      <td data-label="Cliente" class="cel-cliente"><b>${esc(c.nome)}</b><br><span class="sub">cód. ${esc(c.codigo)}</span></td>
      <td data-label="Município">${esc(c.cidade || '—')}</td>
      <td data-label="Curva"><span class="tag ${esc(c.curva || '')}">${esc(c.curva || '—')}</span></td>
      <td data-label="Vol 12m" class="num">${brl(c.vol_12m)}</td>
      <td data-label="Última visita" class="num">${dataBR(c.ultima_visita)}</td>
      <td data-label="Dias sem visita" class="num">${dias}</td>
      <td data-label="Ciclo" class="num">${c.ciclo} dias</td>
      <td data-label="Vendedor">${esc(c.vendedor || '—')}</td></tr>`;
  }).join('');
  if (linhas.length > 400) {
    tb.insertAdjacentHTML('beforeend',
      `<tr class="linha-aviso"><td colspan="8" class="explica">Mostrando 400 de ${linhas.length}. Refine o filtro ou baixe o CSV.</td></tr>`);
  }
}

$('c-curvas').onchange = carregarCobertura;
$('c-filtro').onchange = desenharCobertura;
$('c-municipio').oninput = desenharCobertura;

$('c-exportar').onclick = () => {
  const linhas = filtrarCobertura();
  const cab = ['codigo', 'nome', 'municipio', 'curva', 'vol_12m', 'ultima_visita', 'dias_sem_visita', 'ciclo', 'vendedor'];
  const csv = [cab.join(';')].concat(linhas.map(c => [
    c.codigo, c.nome, c.cidade, c.curva, String(c.vol_12m).replace('.', ','),
    c.ultima_visita || '', c.dias === null ? 'nunca' : c.dias, c.ciclo, c.vendedor || ''
  ].map(v => `"${String(v == null ? '' : v).replace(/"/g, '""')}"`).join(';'))).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  a.download = 'cobertura_carteira.csv';
  a.click();
  URL.revokeObjectURL(a.href);
};

/* ---------------------------------------------------------------- fichas */
let opcoesCarregadas = false;

async function carregarFichas() {
  const q = new URLSearchParams();
  const mapa = { mes: 'f-mes', tipo: 'f-tipo', municipio: 'f-mun', usuario: 'f-usuario', nivel: 'f-nivel', busca: 'f-busca' };
  for (const [param, id] of Object.entries(mapa)) {
    const v = $(id).value.trim();
    if (v) q.set(param, v);
  }
  const r = await fetch('/api/gestor/fichas?' + q.toString());
  if (!r.ok) return;
  const d = await r.json();

  if (!opcoesCarregadas) {
    const enche = (id, itens) => {
      const el = $(id);
      el.innerHTML = el.children[0].outerHTML + itens.map(i => `<option value="${esc(i)}">${esc(i)}</option>`).join('');
    };
    enche('f-mes', d.opcoes.meses);
    enche('f-mun', d.opcoes.municipios);
    enche('f-usuario', d.opcoes.usuarios);
    opcoesCarregadas = true;
  }

  $('contagem-fichas').textContent = d.fichas.length + ' ficha(s). Clique para abrir o relato completo.';
  $('lista-gestor').innerHTML = d.fichas.map(cartaoFicha).join('') ||
    '<div class="vazio">Nenhuma ficha com esses filtros.</div>';
  document.querySelectorAll('.ficha-cab').forEach(c =>
    c.onclick = () => c.parentElement.classList.toggle('aberta'));
}

function cartaoFicha(f) {
  const selo = n => `<span class="selo ${n}">${n === 'forte' ? 'evidência forte' : n === 'media' ? 'evidência média' : 'evidência leve'}</span>`;
  const extra = Object.entries(f.extra || {}).map(([k, v]) => {
    const valor = Array.isArray(v)
      ? v.map(i => `${esc(i.item)}: ${esc(i.preco)}`).join(' · ')
      : esc(v);
    return `<div><span>${esc(k.replace(/_/g, ' '))}</span>${valor}</div>`;
  }).join('');

  const geo = (f.lat != null && f.lon != null)
    ? `<div class="bloco"><h4>Check-in</h4><p>${f.lat.toFixed(5)}, ${f.lon.toFixed(5)}
        ${f.precisao ? '(±' + Math.round(f.precisao) + ' m)' : ''}
        — <a class="link-mapa" target="_blank" rel="noopener"
        href="https://www.google.com/maps?q=${f.lat},${f.lon}">ver no mapa</a></p></div>`
    : `<div class="bloco"><h4>Check-in</h4><p>sem localização registrada</p></div>`;

  return `<div class="ficha">
    <div class="ficha-cab">
      <div><b>${esc(f.cliente_nome)}</b>
        <div class="sub">${esc(f.tipo)} · ${esc(f.municipio || '—')} · ${dataBR(f.criado_em_disp || f.recebido_em)}
        · ${esc(f.usuario_login)}${f.prospect ? ' · <b>cliente novo</b>' : ''}</div></div>
      <div class="ficha-selos">
        ${selo(f.nivel_evidencia || 'leve')}
        ${f.conta_indicador ? '' : '<span class="selo pendente">sem próximo passo</span>'}
      </div>
    </div>
    <div class="ficha-corpo">
      <div class="bloco"><h4>Objetivo</h4><p>${esc(f.objetivo || '—')}</p></div>
      <div class="bloco"><h4>O que aconteceu</h4><p>${esc(f.relato || '—')}</p></div>
      ${f.relato_curto ? '<div class="aviso-curto">Relato abaixo de 200 caracteres — pouco detalhe para virar inteligência de mercado.</div>' : ''}
      <div class="bloco"><h4>Próximo passo</h4>
        <p class="passo">${esc(f.proximo_passo || 'não registrado')}
        ${f.prox_responsavel ? '<br><small>quem: ' + esc(f.prox_responsavel) + '</small>' : ''}
        ${f.prox_data ? '<br><small>quando: ' + dataBR(f.prox_data) + '</small>' : ''}
        ${f.encaminhado_para ? '<br><small>encaminhado para: ' + esc(f.encaminhado_para) + '</small>' : ''}</p></div>
      ${extra ? `<div class="bloco"><h4>Detalhes do tipo</h4><div class="grade-extra">${extra}</div></div>` : ''}
      ${geo}
      ${f.foto_arquivo ? `<div class="bloco"><h4>Foto</h4><img class="ficha-foto" src="/foto/${esc(f.foto_arquivo)}" alt="foto da visita"></div>` : ''}
    </div></div>`;
}

let tempo;
$('f-busca').oninput = () => { clearTimeout(tempo); tempo = setTimeout(carregarFichas, 350); };
['f-mes', 'f-tipo', 'f-mun', 'f-usuario', 'f-nivel'].forEach(id => $(id).onchange = carregarFichas);

carregarCobertura();
