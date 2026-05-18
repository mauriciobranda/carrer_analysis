# Career Fit Analyzer — Instruções para Claude

## Comportamento padrão

Quando o usuário colar uma URL do LinkedIn (ex: `https://www.linkedin.com/jobs/view/XXXXXXXXX/`), **execute imediatamente** sem pedir confirmação:

**Fluxo preferencial com Playwright MCP** (se disponível):
1. Use a ferramenta `playwright` MCP para navegar até a URL e extrair o texto da página
2. Salve o conteúdo em `/tmp/vaga_linkedin.txt`
3. Execute: `python3 linkedin_analyzer.py 'URL_COLADA' -f /tmp/vaga_linkedin.txt`

**Fluxo fallback** (se Playwright não estiver disponível):
```bash
python3 linkedin_analyzer.py 'URL_COLADA'
```

Não pergunte, não explique, não confirme. Cole a URL → rode o script → mostre o resultado.

**Importante sobre calibração:** o script faz 5 perguntas interativas de auto-avaliação (0–3) após a análise. Quando rodado via Claude Code (sem terminal interativo), simule as respostas com `printf` para demonstrar o fluxo completo:
```bash
printf '0\n2\n3\n3\n1\n' | python3 linkedin_analyzer.py 'URL' -f /tmp/vaga_linkedin.txt
```
Informe o usuário que as respostas foram simuladas e que ele deve rodar no terminal com suas respostas reais.

## O que é este projeto

Script Python que analisa o fit de vagas do LinkedIn contra o perfil do candidato (`PROFILE.md`) e plano de desenvolvimento (`PDI.md`). Usa a API do Gemini (gemini-2.5-flash) para a análise.

**Scoring:** Experiência (30pts) + Skills (40pts) + Função (30pts) = 100pts + PDI alignment (30pts)

**Calibração técnica (pós-análise):**
Após exibir o resultado inicial, o script entra automaticamente no modo de calibração:
1. O Gemini gera 5 perguntas curtas sobre as skills técnicas mais críticas da vaga
2. O usuário responde com 0–3 (0 = nunca usei, 3 = domínio/liderança)
3. Uma segunda chamada ao Gemini recalibra apenas o Skills score (0–40pts)
4. O script exibe o diff antes/depois e salva o resultado calibrado

Objetivo: corrigir o viés de auto-avaliação positiva do `context/PROFILE.md`.

**Extração da vaga:**
1. Scraping direto
2. Jina AI Reader (`r.jina.ai/URL`) como bypass automático se LinkedIn bloquear
3. Fallback interativo (Ctrl+D)

## Arquivos do projeto

| Arquivo | Função |
|---|---|
| `linkedin_analyzer.py` | Script principal |
| `context/PROFILE.md` | Perfil profissional do candidato (base da comparação) |
| `context/PDI.md` | Plano de desenvolvimento individual — 3 verticais: Tech, Business, Construído |
| `.env` | `GEMINI_API_KEY` e `GEMINI_MODEL` |
| `results/` | JSONs com histórico de análises |
| `career_analysis.db` | SQLite com todas as análises |

## Como rodar

```bash
# Uso padrão (só a URL)
python3 linkedin_analyzer.py 'https://www.linkedin.com/jobs/view/XXXXXXXXX/'

# Com arquivo de texto da vaga
python3 linkedin_analyzer.py 'URL' -f vaga.txt

# Sem salvar resultado
python3 linkedin_analyzer.py 'URL' --no-save
```

Requer `.env` com `GEMINI_API_KEY=...`

## Candidato

Mauricio Toscan Brandalise — Gerente de Pré-vendas Técnicas | CoE IA & Hiperautomação, 12+ anos, mercado BR/LATAM.

> Nota: `context/PROFILE.md` ainda tem campos `[...]` para preencher com dados reais.
