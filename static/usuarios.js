/* REP Campo - gestao de usuarios */
'use strict';
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function msg(texto, erro) {
  $('msg').innerHTML = `<div class="alerta ${erro ? 'erro' : 'info'}">${esc(texto)}</div>`;
  setTimeout(() => { $('msg').innerHTML = ''; }, 4000);
}

const ERROS = {
  login_ja_existe: 'Já existe usuário com esse login.',
  senha_curta: 'A senha precisa de pelo menos 8 caracteres.',
  login_e_nome_obrigatorios: 'Informe nome e login.',
  nao_pode_desativar_a_si_mesmo: 'Você não pode desativar a si mesmo.',
  nao_pode_rebaixar_a_si_mesmo: 'Você não pode tirar o próprio acesso de admin.',
  so_admin_promove_admin: 'Só um admin pode promover outro admin.',
};

async function carregar() {
  const r = await fetch('/api/gestor/usuarios');
  if (!r.ok) return;
  const d = await r.json();
  document.querySelector('#tab-usuarios tbody').innerHTML = d.usuarios.map(u => {
    const eu = u.id === d.eu;
    return `<tr class="${u.ativo ? '' : 'vencido'}">
      <td data-label="Nome"><b>${esc(u.nome)}</b>${eu ? ' <span class="tag">você</span>' : ''}</td>
      <td data-label="Login">${esc(u.login)}</td>
      <td data-label="Papel">${ {admin:'Admin', gestor:'Gestor', rep:'Representante'}[u.papel] || u.papel }</td>
      <td data-label="Situação">${u.ativo ? '<span class="selo forte">ativo</span>'
                                          : '<span class="selo leve">inativo</span>'}</td>
      <td data-label="Ações">
        <button class="btn-sec" data-senha="${u.id}">Redefinir senha</button>
        ${eu ? '' : `<button class="btn-sec" data-ativo="${u.id}" data-valor="${u.ativo ? 0 : 1}">
          ${u.ativo ? 'Desativar' : 'Reativar'}</button>`}
      </td></tr>`;
  }).join('');

  document.querySelectorAll('[data-senha]').forEach(b => b.onclick = async () => {
    const nova = prompt('Nova senha para este usuário (mínimo 8 caracteres):');
    if (nova === null) return;
    if (nova.length < 8) return msg('Senha muito curta.', true);
    const r = await fetch('/api/gestor/usuarios/' + b.dataset.senha,
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ senha: nova }) });
    const j = await r.json();
    r.ok ? msg('Senha redefinida. Peça para a pessoa trocar no primeiro acesso.')
         : msg(ERROS[j.erro] || 'Não foi possível redefinir.', true);
  });

  document.querySelectorAll('[data-ativo]').forEach(b => b.onclick = async () => {
    const r = await fetch('/api/gestor/usuarios/' + b.dataset.ativo,
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ativo: Number(b.dataset.valor) === 1 }) });
    const j = await r.json();
    if (r.ok) { msg('Situação alterada.'); carregar(); }
    else msg(ERROS[j.erro] || 'Não foi possível alterar.', true);
  });
}

$('form-novo').addEventListener('submit', async ev => {
  ev.preventDefault();
  const corpo = {
    nome: $('n-nome').value.trim(), login: $('n-login').value.trim().toLowerCase(),
    papel: $('n-papel').value, senha: $('n-senha').value,
  };
  const r = await fetch('/api/gestor/usuarios', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo) });
  const j = await r.json();
  if (r.ok) { msg('Usuário ' + j.login + ' criado.'); ev.target.reset(); carregar(); }
  else msg(ERROS[j.erro] || 'Não foi possível criar.', true);
});

carregar();
