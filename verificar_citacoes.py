#!/usr/bin/env python3
"""Confere os numeros de linha citados no MIGRACAO_VERCEL.md contra o codigo atual.

O documento cita linha do codigo em dezenas de lugares. O Ricardo empurra commit
todo dia, e cada push desloca essas linhas. Rodar isto depois de cada pull diz
quais citacoes mentem, e com --corrigir reescreve os numeros no documento.

    python3 verificar_citacoes.py            # so relata
    python3 verificar_citacoes.py --corrigir # reescreve o documento

BASE e o commit contra o qual o texto foi escrito. Depois de um --corrigir bem
sucedido, atualize BASE para o commit conferido.
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DOC = RAIZ / "MIGRACAO_VERCEL.md"
BASE = "7f3dc5c"
MANUAL = {}
PADRAO = "app.py"
ARQUIVOS = {
    "app.js": "static/app.js",
    "sw.js": "static/sw.js",
    "painel.js": "static/painel.js",
    "viagens.js": "static/viagens.js",
    "importar_carteira.py": "importar_carteira.py",
    "criar_usuario.py": "criar_usuario.py",
    "gerar_pdf.py": "gerar_pdf.py",
    "app.py": "app.py",
}
CITACAO = re.compile(r"linhas? \d+(?:\s*(?:,|a|e)\s*\d+)*")
NUMERO = re.compile(r"\d+")


def versao(ref, caminho):
    saida = subprocess.run(["git", "-C", str(RAIZ), "show", f"{ref}:{caminho}"],
                           capture_output=True, text=True)
    if saida.returncode:
        return None
    return saida.stdout.splitlines()


def paragrafos(texto):
    linhas = texto.splitlines()
    blocos, atual, inicio = [], [], 0
    for i, linha in enumerate(linhas):
        if linha.strip():
            if not atual:
                inicio = i
            atual.append(linha)
        elif atual:
            blocos.append((inicio, atual))
            atual = []
    if atual:
        blocos.append((inicio, atual))
    return linhas, blocos


def candidatos(bloco, alvo_offset):
    """Ordena os arquivos citados no paragrafo pela distancia ate a citacao.

    Um paragrafo cita mais de um arquivo. "a linha 607 ... da linha 596 do
    app.js" fala de dois. Vence o nome mencionado mais perto, e o app.py entra
    sempre no fim como ultima tentativa."""
    junto = "\n".join(bloco)
    posicoes = {}
    for apelido in ARQUIVOS:
        for m in re.finditer(re.escape(apelido), junto):
            posicoes.setdefault(apelido, []).append(m.start())
    ordem = sorted(posicoes,
                   key=lambda a: min(abs(o - alvo_offset) for o in posicoes[a]))
    lista = [ARQUIVOS[a] for a in ordem]
    if PADRAO not in lista:
        lista.append(PADRAO)
    return lista


def localizar(texto, novo, antigo, velha):
    if velha <= len(novo) and novo[velha - 1].rstrip() == texto:
        return velha, "parada"
    achados = [i for i, l in enumerate(novo) if l.rstrip() == texto]
    if len(achados) == 1:
        return achados[0] + 1, "unico"
    if not achados:
        return None, "sumiu"
    vizinhos = [antigo[velha - 2].rstrip() if velha >= 2 else "",
                antigo[velha].rstrip() if velha < len(antigo) else ""]
    melhor, pontos = None, -1
    for i in achados:
        p = 0
        if i >= 1 and novo[i - 1].rstrip() == vizinhos[0]:
            p += 1
        if i + 1 < len(novo) and novo[i + 1].rstrip() == vizinhos[1]:
            p += 1
        if p > pontos:
            melhor, pontos = i, p
        elif p == pontos:
            melhor = None
    if melhor is None:
        return None, "ambiguo"
    return melhor + 1, "vizinho"


def main():
    corrigir = "--corrigir" in sys.argv
    texto = DOC.read_text(encoding="utf-8")
    linhas, blocos = paragrafos(texto)
    cache = {}
    trocas, quebradas, iguais = [], [], 0

    for inicio, bloco in blocos:
        junto = "\n".join(bloco)
        for m in CITACAO.finditer(junto):
            for n in NUMERO.finditer(m.group(0)):
                velha = int(n.group(0))
                ini, fim = m.start() + n.start(), m.start() + n.end()
                falha = None
                for caminho in candidatos(bloco, ini):
                    if caminho not in cache:
                        atual = RAIZ / caminho
                        if not atual.exists():
                            continue
                        cache[caminho] = (versao(BASE, caminho),
                                          atual.read_text(encoding="utf-8").splitlines())
                    antigo, novo_arq = cache[caminho]
                    if antigo is None or velha > len(antigo):
                        continue
                    conteudo = antigo[velha - 1].rstrip()
                    if not conteudo.strip():
                        continue
                    nova = MANUAL.get((caminho, velha))
                    como = "mapa manual"
                    if nova is None:
                        nova, como = localizar(conteudo, novo_arq, antigo, velha)
                    if nova is None:
                        falha = (caminho, velha, como + ": " + conteudo.strip()[:60], inicio + 1)
                        continue
                    falha = None
                    if nova == velha:
                        iguais += 1
                    else:
                        trocas.append((inicio, ini, fim, caminho, velha, nova, como))
                    break
                else:
                    falha = falha or (PADRAO, velha, "nenhum arquivo candidato serve", inicio + 1)
                if falha:
                    quebradas.append(falha)

    for caminho, velha, motivo, no_doc in quebradas:
        print(f"QUEBRADA  {caminho}:{velha}  (doc linha {no_doc})  {motivo}")
    for _, _, _, caminho, velha, nova, como in trocas:
        print(f"MUDOU     {caminho}:{velha} -> {nova}  ({como})")
    print(f"\n{iguais} iguais, {len(trocas)} deslocadas, {len(quebradas)} sem correspondencia")

    if corrigir and quebradas:
        print("\nnada reescrito. resolva as quebradas primeiro, no MANUAL ou no texto.")
        return 1

    if corrigir and trocas:
        blocos_por_inicio = {i: b for i, b in blocos}
        for inicio, ini, fim, _, _, nova, _ in sorted(trocas, key=lambda t: (-t[0], -t[1])):
            bloco = blocos_por_inicio[inicio]
            junto = "\n".join(bloco)
            junto = junto[:ini] + str(nova) + junto[fim:]
            novo_bloco = junto.split("\n")
            for k, linha in enumerate(novo_bloco):
                linhas[inicio + k] = linha
            blocos_por_inicio[inicio] = novo_bloco
        DOC.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        atual = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True).stdout.strip()
        fonte = Path(__file__)
        fonte.write_text(re.sub(r'BASE = "[0-9a-f]+"', f'BASE = "{atual}"',
                                fonte.read_text(encoding="utf-8"), count=1)
                         .replace(re.search(r"MANUAL = \{.*?\}\n", fonte.read_text(encoding="utf-8"),
                                            re.S).group(0), "MANUAL = {}\n"),
                         encoding="utf-8")
        print(f"documento reescrito: {len(trocas)} numeros. BASE agora e {atual}.")

    return 1 if quebradas else 0


if __name__ == "__main__":
    sys.exit(main())
