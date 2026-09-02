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
  if (b.dataset.tela === 'ocorrencias') carregarOcorrencias();
  if (b.dataset.tela === 'experiencia') carregarExperiencia();
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


/* ---------------------------------------------------------- ocorrencias */
async function carregarOcorrencias() {
  const r = await fetch('/api/gestor/ocorrencias?situacao=' + $('o-situacao').value);
  if (!r.ok) return;
  const d = await r.json();

  $('cartoes-oc').innerHTML = `
    <div class="cartao"><div class="num ${d.abertas ? 'num-alerta' : ''}">${d.abertas}</div>
      <div class="rot">ocorrências abertas</div></div>
    <div class="cartao"><div class="num">${d.resolvidas}</div>
      <div class="rot">resolvidas</div></div>
    <div class="cartao"><div class="num">${d.ocorrencias.filter(o => (o.dias_aberta || 0) > 7 && o.ocorrencia_status === 'aberta').length}</div>
      <div class="rot">abertas há mais de 7 dias</div></div>`;

  $('lista-oc').innerHTML = d.ocorrencias.map(o => {
    const velha = o.ocorrencia_status === 'aberta' && (o.dias_aberta || 0) > 7;
    return `<div class="ficha">
      <div class="ficha-cab">
        <div><b>${esc(o.ocorrencia_num)} · ${esc(o.cliente_nome)}</b>
          <div class="sub">${esc(o.problema_tipo || 'sem tipo')} · ${esc(o.municipio || '—')}
            · aberta há ${o.dias_aberta} dia(s) · ${esc(o.usuario_login)}</div></div>
        <div class="ficha-selos">
          ${o.ocorrencia_status === 'aberta'
            ? `<span class="selo ${velha ? 'pendente' : 'media'}">${velha ? 'atrasada' : 'aberta'}</span>
               <button class="btn-sec" data-resolver="${esc(o.ocorrencia_num)}">Marcar resolvida</button>`
            : '<span class="selo forte">resolvida</span>'}
        </div>
      </div>
      <div class="ficha-corpo">
        <div class="bloco"><h4>Relato</h4><p>${esc(o.relato || '—')}</p></div>
        <div class="bloco"><h4>Próximo passo</h4>
          <p class="passo">${esc(o.proximo_passo || '—')}
          ${o.prox_responsavel ? '<br><small>quem: ' + esc(o.prox_responsavel) + '</small>' : ''}
          ${o.encaminhado_para ? '<br><small>encaminhado: ' + esc(o.encaminhado_para) + '</small>' : ''}</p></div>
        ${o.foto_arquivo ? `<div class="bloco"><h4>Foto</h4><img class="ficha-foto" src="/foto/${esc(o.foto_arquivo)}" alt="foto da ocorrência"></div>` : ''}
      </div></div>`;
  }).join('') || '<div class="vazio">Nenhuma ocorrência nessa situação.</div>';

  document.querySelectorAll('.ficha-cab').forEach(c => c.onclick = ev => {
    if (ev.target.dataset.resolver) return;
    c.parentElement.classList.toggle('aberta');
  });
  document.querySelectorAll('[data-resolver]').forEach(b => b.onclick = async ev => {
    ev.stopPropagation();
    const n = b.dataset.resolver;
    if (!confirm('Marcar ' + n + ' como resolvida?')) return;
    const r = await fetch('/api/gestor/ocorrencia/' + n + '/resolver', { method: 'POST' });
    if (r.ok) carregarOcorrencias();
    else alert('Não foi possível resolver essa ocorrência.');
  });
}
$('o-situacao').onchange = carregarOcorrencias;

/* --------------------------------------------------------- experiencia */
async function carregarExperiencia() {
  const r = await fetch('/api/gestor/experiencia');
  if (!r.ok) return;
  const d = await r.json();
  const vazio = v => (v === null || v === undefined) ? '—' : v;

  $('cartoes-exp').innerHTML = `
    <div class="cartao"><div class="num ${d.nps.indice !== null && d.nps.indice < 50 ? 'num-alerta' : ''}">${vazio(d.nps.indice)}</div>
      <div class="rot">NPS relacional<br><small>${d.nps.n} resposta(s)</small></div></div>
    <div class="cartao"><div class="num ${d.csat.pct_bons !== null && d.csat.pct_bons < 80 ? 'num-alerta' : ''}">${d.csat.pct_bons === null ? '—' : d.csat.pct_bons + '%'}</div>
      <div class="rot">CSAT satisfeitos<br><small>${d.csat.n} resposta(s)</small></div></div>
    <div class="cartao"><div class="num ${d.ces.pct_bons !== null && d.ces.pct_bons < 70 ? 'num-alerta' : ''}">${d.ces.pct_bons === null ? '—' : d.ces.pct_bons + '%'}</div>
      <div class="rot">CES acharam fácil<br><small>${d.ces.n} resposta(s)</small></div></div>
    <div class="cartao"><div class="num">${d.nps.n + d.csat.n + d.ces.n}</div>
      <div class="rot">clientes ouvidos</div></div>`;

  const linhas = (bloco, rotulo) => bloco.por_etapa.map(e => `
    <tr><td data-label="Etapa"><b>${esc(e.exp_etapa || '—')}</b></td>
      <td data-label="Respostas" class="num">${e.n}</td>
      <td data-label="Média" class="num"><b>${e.media}</b></td>
      <td data-label="${rotulo}" class="num">${e.bons}</td>
      <td data-label="%" class="num">${Math.round(100 * e.bons / e.n)}%</td></tr>`).join('')
    || `<tr><td colspan="5" class="explica">Nenhuma resposta ainda.</td></tr>`;

  document.querySelector('#tab-csat tbody').innerHTML = linhas(d.csat, 'Satisfeitos');
  document.querySelector('#tab-ces tbody').innerHTML = linhas(d.ces, 'Acharam fácil');

  const selo = m => m === 'nps' ? 'NPS' : m === 'ces' ? 'CES' : 'CSAT';
  $('lista-verbatim').innerHTML = d.comentarios.map(c => `
    <div class="ficha"><div class="ficha-cab">
      <div><b>${esc(c.cliente_nome)}</b>
        <div class="sub">${esc(selo(c.exp_metrica))} · ${esc(c.exp_etapa || '—')} · ${dataBR(c.recebido_em)}</div>
        <p style="margin:8px 0 0;font-size:.92rem">"${esc(c.exp_comentario)}"</p></div>
      <div class="ficha-selos"><span class="selo ${c.exp_nota >= 8 ? 'forte' : c.exp_nota <= 6 ? 'pendente' : 'media'}">nota ${c.exp_nota}</span></div>
    </div></div>`).join('') || '<div class="vazio">Nenhum comentário registrado.</div>';
}
