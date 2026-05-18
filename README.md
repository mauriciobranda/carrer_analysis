# Career Fit Analyzer

Ferramenta CLI que analisa vagas do LinkedIn contra seu perfil profissional (`PROFILE.md`) e seu plano de desenvolvimento (`PDI.md`), gerando um score de fit e recomendação de candidatura.

## Como funciona

```
Vaga (texto) + PROFILE.md + PDI.md → Gemini 2.5 Flash → Score + Análise + Recomendação
```

**Score de Fit (0–100 pts)**

| Critério    | Peso | O que avalia |
|-------------|------|--------------|
| Experiência | 30   | Anos, seniority, setor, histórico |
| Skills      | 40   | Match técnico e comportamental |
| Função      | 30   | Alinhamento com trajetória e aspirações |

**Alinhamento PDI (0–30 pts)**

| Vertical    | Peso | O que avalia |
|-------------|------|--------------|
| Tech        | 10   | Quanto a vaga acelera crescimento técnico em IA/Automação |
| Business    | 10   | Quanto desenvolve liderança, estratégia e visão executiva |
| Construído  | 10   | Quanto agrega ao portfólio e reputação pública |

**Critério de decisão:**
- Fit ≥ 70 + PDI ≥ 21 → Candidatura prioritária
- Fit ≥ 55 + PDI ≥ 15 → Vale explorar
- Abaixo disso → Não priorizar

---

## Setup

### 1. Dependências

```bash
pip install -r requirements.txt
```

### 2. Chave de API

```bash
cp .env.example .env
```

Edite `.env` e coloque sua chave do Google AI Studio:

```
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
```

Obtenha a chave em: https://aistudio.google.com/apikey

### 3. Preencha seu perfil

Edite `PROFILE.md` com seus dados reais. Os campos entre `[...]` são placeholders — quanto mais completo, melhor a análise.

---

## Uso

### Fluxo padrão — só cole o link

```bash
python linkedin_analyzer.py 'https://linkedin.com/jobs/view/4400248155/'
```

O script tenta extrair o conteúdo da vaga automaticamente em duas etapas:
1. Scraping direto da URL
2. Se bloqueado (como no LinkedIn), usa o **Jina AI Reader** — serviço gratuito que contorna esses bloqueios

Na maioria dos casos, só o link basta.

### Se a extração automática falhar

O script cai em modo interativo: basta colar o texto da vaga e pressionar `Ctrl+D`.

### Outros flags

```bash
# Usar um arquivo .txt com o texto da vaga (fallback manual)
python linkedin_analyzer.py 'https://...' -f vaga.txt

# Analisar sem salvar resultado
python linkedin_analyzer.py 'https://...' --no-save
```

---

## Saída

### Terminal

```
════════════════════════════════════════════════════════════════
  ANÁLISE DE FIT DE CARREIRA
════════════════════════════════════════════════════════════════

  Vaga      : Senior Sales Engineer - Brazil
  Empresa   : Datadog
  ...

  FIT SCORE : 89/100  —  EXCELENTE FIT 🟢
────────────────────────────────────────────────────────────────
  Experiência   28/30 pts
  Skills        36/40 pts  ✅ Tenho: Presales, IA...  ❌ Gap: Observability
  Função        25/30 pts
  ...

  RECOMENDAÇÃO: APLICAR
  ...

  ALINHAMENTO COM PDI
  Tech        ██████████  9/10
  Business    ████████░░  8/10
  Construído  █████████░  9/10
  Total PDI   26/30
```

### Arquivos gerados

| Tipo   | Local                          | Conteúdo |
|--------|--------------------------------|----------|
| JSON   | `results/YYYYMMDD_HHMMSS_empresa.json` | Análise completa estruturada |
| SQLite | `career_analysis.db`           | Histórico de todas as análises |

### Consultar histórico (SQLite)

```bash
sqlite3 career_analysis.db "SELECT consulted_at, company, fit_total, recommendation FROM job_analyses ORDER BY fit_total DESC;"
```

---

## Estrutura do projeto

```
Carrer_Analysis/
├── linkedin_analyzer.py   # Script principal
├── PROFILE.md             # Seu perfil profissional (personalizar!)
├── PDI.md                 # Plano de Desenvolvimento Individual
├── .env                   # Chave de API (não comitar)
├── .env.example           # Template do .env
├── requirements.txt       # Dependências Python
├── career_analysis.db     # Histórico (gerado automaticamente)
└── results/               # JSONs de cada análise
```

---

## Personalizando a análise

### PROFILE.md

Preencha todos os `[...]` com seus dados reais:
- Empresa atual e período
- Métricas concretas (pipeline $Xm, taxa de conversão %)
- Certificações, idiomas, pretensão salarial
- Ferramentas específicas que você usa (UiPath, Azure OpenAI, etc.)

Quanto mais específico, mais preciso o score.

### PDI.md

Atualize o status dos milestones conforme avançar (⬜ → 🟡 → 🟢). Isso afina o alinhamento calculado para cada vaga.

### Modelo Gemini

Para mudar o modelo, edite `.env`:

```
GEMINI_MODEL=gemini-2.5-pro   # mais preciso, mais lento
GEMINI_MODEL=gemini-2.5-flash # padrão — bom equilíbrio custo/qualidade
```
