#!/usr/bin/env python3
"""LinkedIn Career Fit Analyzer — compara uma vaga com PROFILE.md e PDI.md"""

import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from google import genai
except ImportError:
    sys.exit(
        "Erro: pacote 'google-genai' não instalado.\n"
        "Instale as dependências com: pip install -r requirements.txt"
    )

SCRIPT_DIR = Path(__file__).parent
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
DB_PATH = SCRIPT_DIR / "career_analysis.db"


# ─── Carregamento de arquivos ────────────────────────────────────────────────

def load_file(filename: str) -> str:
    path = SCRIPT_DIR / filename
    if not path.exists():
        sys.exit(f"Erro: {filename} não encontrado em {SCRIPT_DIR}")
    return path.read_text(encoding="utf-8")


# ─── Obtenção do conteúdo da vaga ────────────────────────────────────────────

def fetch_url(url: str) -> str:
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return ""


def fetch_via_jina(url: str) -> str:
    """Usa o Jina AI Reader para converter qualquer URL em texto legível."""
    try:
        import requests
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "text/plain",
            "X-Return-Format": "text",
        }
        resp = requests.get(jina_url, headers=headers, timeout=30)
        if resp.status_code == 200 and len(resp.text) > 300:
            return resp.text
    except Exception:
        pass
    return ""


def html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:12000]
    except ImportError:
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text)[:12000]


def get_job_content(url: str, file_path: str | None) -> str:
    # Modo arquivo: conteúdo colado/salvo em .txt
    if file_path:
        p = Path(file_path)
        if not p.exists():
            sys.exit(f"Erro: arquivo '{file_path}' não encontrado.")
        return p.read_text(encoding="utf-8")

    # Tentativa 1: scraping direto
    print(f"Buscando vaga...")
    html = fetch_url(url)
    if html:
        text = html_to_text(html)
        if len(text) > 300:
            print("Conteúdo extraído com sucesso.\n")
            return text

    # Tentativa 2: Jina AI Reader (contorna bloqueios do LinkedIn)
    print("Tentando via Jina AI Reader...")
    text = fetch_via_jina(url)
    if text:
        print("Conteúdo extraído com sucesso.\n")
        return text[:12000]

    # Fallback: modo paste
    print(
        "\nNão foi possível extrair a vaga automaticamente.\n"
        "Cole o conteúdo da vaga abaixo e pressione Ctrl+D ao terminar:\n"
    )
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines)


# ─── Análise com Gemini ───────────────────────────────────────────────────────

ANALYSIS_PROMPT = """Você é um especialista sênior em recrutamento executivo e desenvolvimento de carreira.

Analise a vaga abaixo e calcule o fit score com o perfil do candidato.

## URL da Vaga
{url}

## Descrição da Vaga
{job_content}

## Perfil do Candidato (PROFILE.md)
{profile}

## PDI do Candidato (PDI.md)
{pdi}

## Critérios de Pontuação
- **Experiência (0–30 pts):** Anos de experiência, seniority, setor, histórico relevante
- **Skills (0–40 pts):** Match técnico e comportamental com os requisitos da vaga
- **Função (0–30 pts):** Alinhamento da função com trajetória e aspirações de carreira

## Calibração técnica
Liste exatamente 5 skills técnicas CRÍTICAS da vaga para auto-avaliação de proficiência.
REGRA: o campo "pergunta" deve ser uma descrição CURTA (máx. 10 palavras) da tecnologia ou competência.
Formato correto: "Informatica MDM / Data Integration" ou "Apache Spark — tuning e otimização"
Formato ERRADO: "Descreva um projeto..." ou "Como você abordaria..."
NÃO gere perguntas abertas. Apenas o nome/contexto da skill.

## Resposta
Retorne APENAS um JSON válido com esta estrutura exata (sem texto antes ou depois):

{{
  "vaga": {{
    "titulo": "",
    "empresa": "",
    "localizacao": "",
    "modalidade": "presencial | remoto | híbrido",
    "nivel": "analista | pleno | sênior | gerente | diretor | VP | C-level",
    "descricao_resumida": "",
    "requisitos_principais": [],
    "skills_tecnicas": [],
    "skills_comportamentais": [],
    "beneficios_destacados": [],
    "calibration_questions": [
      {{"skill": "", "pergunta": "", "nivel_exigido": "basico | intermediario | avancado | especialista"}}
    ]
  }},
  "fit_score": {{
    "total": 0,
    "experiencia": {{
      "pontos": 0,
      "max": 30,
      "justificativa": ""
    }},
    "skills": {{
      "pontos": 0,
      "max": 40,
      "justificativa": "",
      "matches": [],
      "gaps": []
    }},
    "funcao": {{
      "pontos": 0,
      "max": 30,
      "justificativa": ""
    }}
  }},
  "analise": {{
    "pontos_fortes": [],
    "gaps_principais": [],
    "oportunidades": [],
    "riscos": []
  }},
  "recomendacao": {{
    "nivel": "APLICAR | APLICAR COM RESSALVAS | NÃO APLICAR",
    "justificativa": "",
    "proximos_passos": [],
    "customizacao_cv": []
  }},
  "alinhamento_pdi": {{
    "vertical_tech": 0,
    "vertical_business": 0,
    "vertical_construido": 0,
    "comentario": ""
  }}
}}"""


def analyze(url: str, job_content: str, profile: str, pdi: str, client=None) -> dict:
    if client is None:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    prompt = ANALYSIS_PROMPT.format(
        url=url,
        job_content=job_content,
        profile=profile,
        pdi=pdi,
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={
            "max_output_tokens": 16384,
            "response_mime_type": "application/json",
        },
    )

    raw = response.text.strip()

    # Remove cercas de código se presentes
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"\nErro ao parsear resposta do Gemini: {e}")
        print("Resposta bruta:\n", raw)
        sys.exit(1)


# ─── Calibração técnica interativa ───────────────────────────────────────────

RECALIBRATION_PROMPT = """Você é um especialista em recrutamento técnico conhecido por avaliações honestas e críticas.

O candidato acabou de responder um questionário de auto-avaliação das skills técnicas mais críticas da vaga.
Recalibre APENAS o score de Skills (0–40 pts) com base nessas respostas reais.

## Score original de Skills
Pontos: {original_pontos}/40
Justificativa original: {original_justificativa}

## Respostas do candidato (escala 0–3)
0 = Nunca usei / só ouvi falar
1 = Noções básicas / vi em demos
2 = Usei em projetos reais, mas não profundamente
3 = Domínio — uso com frequência, consigo liderar discussões

{respostas_formatadas}

## Regras de recalibração
- Seja crítico: respostas 0–1 em skills marcadas como "avancado" ou "especialista" penalizam proporcionalmente.
- Respostas 3 em todas não devem mudar o score original (já era alto).
- O objetivo é corrigir otimismo excessivo no PROFILE.md declarado, não punir conhecimento legítimo.
- total_recalibrado = {exp_pts} (experiência, imutável) + skills_recalibrados.pontos + {fn_pts} (função, imutável)

Retorne APENAS JSON válido:

{{
  "skills_recalibrados": {{
    "pontos": 0,
    "max": 40,
    "justificativa": "",
    "matches": [],
    "gaps": []
  }},
  "total_recalibrado": 0,
  "comentario_calibracao": ""
}}"""

_SCALE_LABELS = [
    "Nunca usei / só ouvi falar",
    "Noções básicas / vi em demos",
    "Usei em projetos reais, mas não profundamente",
    "Domínio — uso com frequência, liderança técnica",
]


def ask_calibration(questions: list) -> list:
    W = 64
    print(f"\n{'═' * W}")
    print("  CALIBRAÇÃO TÉCNICA — Skills Score")
    print(f"{'═' * W}")
    print()
    print("  Seja honesto — isso vai calibrar o score de Skills.")
    print()
    print("  0 = Nunca usei / só ouvi falar")
    print("  1 = Noções básicas / vi em demos")
    print("  2 = Usei em projetos reais, mas não profundamente")
    print("  3 = Domínio — uso com frequência, liderança técnica")
    print()

    answers = []
    for i, q in enumerate(questions[:5], 1):
        skill = q.get("skill", "")
        pergunta = q.get("pergunta", skill) or skill
        nivel = q.get("nivel_exigido", "")
        nivel_str = f"  [{nivel}]" if nivel else ""

        print(f"  {i}. {pergunta}{nivel_str}")
        while True:
            try:
                raw = input("     ❯ ").strip()
                val = int(raw)
                if 0 <= val <= 3:
                    answers.append({
                        "skill": skill,
                        "pergunta": pergunta,
                        "resposta": val,
                        "nivel_exigido": nivel,
                    })
                    break
                print("     Use 0, 1, 2 ou 3.")
            except (ValueError, EOFError):
                print("     Resposta inválida. Use 0, 1, 2 ou 3.")
        print()

    return answers


def recalibrate_skills(result: dict, answers: list, client) -> dict:
    fs = result.get("fit_score", {})
    sk = fs.get("skills", {})
    exp_pts = fs.get("experiencia", {}).get("pontos", 0)
    fn_pts  = fs.get("funcao", {}).get("pontos", 0)

    def _clean(s: str) -> str:
        return s.replace('"', "'").replace('\n', ' ')[:80]

    respostas_formatadas = "\n".join(
        f"  - {_clean(a['skill'])} [{a.get('nivel_exigido', '')}]: {a['resposta']}/3 — {_SCALE_LABELS[a['resposta']]}"
        for a in answers
    )

    justificativa_curta = _clean(sk.get("justificativa", ""))[:200]

    prompt = RECALIBRATION_PROMPT.format(
        original_pontos=sk.get("pontos", 0),
        original_justificativa=justificativa_curta,
        respostas_formatadas=respostas_formatadas,
        exp_pts=exp_pts,
        fn_pts=fn_pts,
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

    import re as _re
    try:
        calibration = json.loads(raw)
    except json.JSONDecodeError:
        match = _re.search(r'\{.*\}', raw, _re.DOTALL)
        if match:
            try:
                calibration = json.loads(match.group())
            except json.JSONDecodeError as e:
                print(f"\nErro ao parsear recalibração: {e}")
                print(f"Resposta bruta: {raw[:300]}")
                return result
        else:
            print(f"\nErro: resposta de recalibração sem JSON. Recebido: {raw[:200]}")
            return result

    original_sk_pts = sk.get("pontos", 0)
    original_total  = fs.get("total", 0)
    new_skills      = calibration.get("skills_recalibrados", {})
    new_total       = calibration.get("total_recalibrado", original_total)

    result["calibration"] = {
        "answers": answers,
        "original_skills_pontos": original_sk_pts,
        "original_total": original_total,
        "new_skills_pontos": new_skills.get("pontos", original_sk_pts),
        "new_total": new_total,
        "comentario": calibration.get("comentario_calibracao", ""),
    }
    result["fit_score"]["skills"] = new_skills
    result["fit_score"]["total"]  = new_total

    return result


def display_questions(questions: list) -> None:
    """Exibe as perguntas de calibração sem pedir resposta (para uso no Claude Code)."""
    W = 64
    print(f"\n{'═' * W}")
    print("  PERGUNTAS DE CALIBRAÇÃO — responda 0-3 no chat")
    print(f"{'═' * W}")
    print()
    print("  0 = Nunca usei / só ouvi falar")
    print("  1 = Noções básicas / vi em demos")
    print("  2 = Usei em projetos reais, mas não profundamente")
    print("  3 = Domínio — uso com frequência, liderança técnica")
    print()
    for i, q in enumerate(questions[:5], 1):
        pergunta = q.get("pergunta", q.get("skill", ""))
        nivel = q.get("nivel_exigido", "")
        nivel_str = f"  [{nivel}]" if nivel else ""
        print(f"  {i}. {pergunta}{nivel_str}")
    print(f"\n{'═' * W}\n")


def display_calibration_result(calibration: dict) -> None:
    W = 64
    sep = "─" * W
    orig_sk    = calibration.get("original_skills_pontos", 0)
    new_sk     = calibration.get("new_skills_pontos", 0)
    orig_total = calibration.get("original_total", 0)
    new_total  = calibration.get("new_total", 0)
    comment    = calibration.get("comentario", "")

    delta_sk    = new_sk - orig_sk
    delta_total = new_total - orig_total
    sign_sk     = f"{delta_sk:+d} pts" if delta_sk != 0 else "sem alteração"
    sign_total  = f"{delta_total:+d} pts" if delta_total != 0 else "sem alteração"

    print(f"\n{sep}")
    print("  RESULTADO APÓS CALIBRAÇÃO")
    print(sep)
    print(f"  Skills : {orig_sk}/40  →  {new_sk}/40  ({sign_sk})")
    print(f"  Total  : {orig_total}/100  →  {new_total}/100  ({sign_total})")
    if comment:
        print(f"\n  {comment}")
    print(f"\n{'═' * W}\n")


# ─── Exibição dos resultados ──────────────────────────────────────────────────

def bar(value: int, max_val: int = 10, width: int = 10) -> str:
    filled = round(value * width / max_val)
    return "█" * filled + "░" * (width - filled)


def display(result: dict) -> None:
    v   = result.get("vaga", {})
    fs  = result.get("fit_score", {})
    an  = result.get("analise", {})
    rec = result.get("recomendacao", {})
    pdi = result.get("alinhamento_pdi", {})

    total = fs.get("total", 0)
    exp   = fs.get("experiencia", {})
    sk    = fs.get("skills", {})
    fn    = fs.get("funcao", {})

    if total >= 80:
        score_tag = "EXCELENTE FIT 🟢"
    elif total >= 60:
        score_tag = "BOM FIT 🟡"
    elif total >= 40:
        score_tag = "FIT PARCIAL 🟠"
    else:
        score_tag = "FIT BAIXO 🔴"

    W = 64
    sep = "─" * W

    print(f"\n{'═' * W}")
    print("  ANÁLISE DE FIT DE CARREIRA")
    print(f"{'═' * W}")
    print(f"\n  Vaga      : {v.get('titulo', 'N/A')}")
    print(f"  Empresa   : {v.get('empresa', 'N/A')}")
    print(f"  Local     : {v.get('localizacao', 'N/A')}  •  {v.get('modalidade', 'N/A')}")
    print(f"  Nível     : {v.get('nivel', 'N/A')}")
    print(f"\n  {v.get('descricao_resumida', '')}")

    print(f"\n{sep}")
    print(f"  FIT SCORE : {total}/100  —  {score_tag}")
    print(sep)
    print(f"  Experiência  {exp.get('pontos', 0):>3}/{exp.get('max', 30)} pts")
    print(f"               {exp.get('justificativa', '')}")
    print()
    print(f"  Skills       {sk.get('pontos', 0):>3}/{sk.get('max', 40)} pts")
    print(f"               {sk.get('justificativa', '')}")
    if sk.get("matches"):
        print(f"               ✅ Tenho  : {', '.join(sk['matches'][:6])}")
    if sk.get("gaps"):
        print(f"               ❌ Gap    : {', '.join(sk['gaps'][:4])}")
    print()
    print(f"  Função       {fn.get('pontos', 0):>3}/{fn.get('max', 30)} pts")
    print(f"               {fn.get('justificativa', '')}")

    print(f"\n{sep}")
    print("  ANÁLISE QUALITATIVA")
    print(sep)

    sections = [
        ("✅ Pontos fortes", an.get("pontos_fortes", [])),
        ("⚠️  Gaps principais", an.get("gaps_principais", [])),
        ("💡 Oportunidades", an.get("oportunidades", [])),
        ("⚡ Riscos", an.get("riscos", [])),
    ]
    for label, items in sections:
        if items:
            print(f"\n  {label}:")
            for item in items:
                print(f"    • {item}")

    print(f"\n{sep}")
    print("  RECOMENDAÇÃO")
    print(sep)
    print(f"\n  {rec.get('nivel', '')}")
    print(f"  {rec.get('justificativa', '')}")

    if rec.get("proximos_passos"):
        print("\n  Próximos passos:")
        for i, step in enumerate(rec["proximos_passos"], 1):
            print(f"    {i}. {step}")

    if rec.get("customizacao_cv"):
        print("\n  Customização do CV:")
        for tip in rec["customizacao_cv"]:
            print(f"    • {tip}")

    print(f"\n{sep}")
    print("  ALINHAMENTO COM PDI")
    print(sep)
    tech  = pdi.get("vertical_tech", 0)
    biz   = pdi.get("vertical_business", 0)
    const = pdi.get("vertical_construido", 0)
    total_pdi = tech + biz + const
    print(f"\n  Tech        {bar(tech)}  {tech}/10")
    print(f"  Business    {bar(biz)}  {biz}/10")
    print(f"  Construído  {bar(const)}  {const}/10")
    print(f"  Total PDI   {total_pdi}/30")
    print(f"\n  {pdi.get('comentario', '')}")

    print(f"\n{'═' * W}\n")


# ─── Persistência ─────────────────────────────────────────────────────────────

def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consulted_at TEXT NOT NULL,
                url TEXT NOT NULL,
                job_title TEXT,
                company TEXT,
                location TEXT,
                modality TEXT,
                seniority TEXT,
                fit_total INTEGER,
                experience_points INTEGER,
                skills_points INTEGER,
                function_points INTEGER,
                technical_knowledge_level INTEGER,
                business_knowledge_level INTEGER,
                built_reputation_level INTEGER,
                pdi_total INTEGER,
                recommendation TEXT,
                summary TEXT,
                strengths_json TEXT,
                gaps_json TEXT,
                opportunities_json TEXT,
                risks_json TEXT,
                next_steps_json TEXT,
                cv_customization_json TEXT,
                json_result_path TEXT,
                raw_analysis_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_job_analyses_company
            ON job_analyses(company)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_job_analyses_consulted_at
            ON job_analyses(consulted_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_job_analyses_fit_total
            ON job_analyses(fit_total)
            """
        )


def save_to_db(result: dict, url: str, timestamp: str, json_result_path: str) -> None:
    vaga = result.get("vaga", {})
    fit = result.get("fit_score", {})
    analise = result.get("analise", {})
    recomendacao = result.get("recomendacao", {})
    pdi = result.get("alinhamento_pdi", {})

    tech = pdi.get("vertical_tech", 0)
    business = pdi.get("vertical_business", 0)
    built = pdi.get("vertical_construido", 0)

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO job_analyses (
                consulted_at,
                url,
                job_title,
                company,
                location,
                modality,
                seniority,
                fit_total,
                experience_points,
                skills_points,
                function_points,
                technical_knowledge_level,
                business_knowledge_level,
                built_reputation_level,
                pdi_total,
                recommendation,
                summary,
                strengths_json,
                gaps_json,
                opportunities_json,
                risks_json,
                next_steps_json,
                cv_customization_json,
                json_result_path,
                raw_analysis_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                url,
                vaga.get("titulo"),
                vaga.get("empresa"),
                vaga.get("localizacao"),
                vaga.get("modalidade"),
                vaga.get("nivel"),
                fit.get("total"),
                fit.get("experiencia", {}).get("pontos"),
                fit.get("skills", {}).get("pontos"),
                fit.get("funcao", {}).get("pontos"),
                tech,
                business,
                built,
                tech + business + built,
                recomendacao.get("nivel"),
                vaga.get("descricao_resumida"),
                json.dumps(analise.get("pontos_fortes", []), ensure_ascii=False),
                json.dumps(analise.get("gaps_principais", []), ensure_ascii=False),
                json.dumps(analise.get("oportunidades", []), ensure_ascii=False),
                json.dumps(analise.get("riscos", []), ensure_ascii=False),
                json.dumps(recomendacao.get("proximos_passos", []), ensure_ascii=False),
                json.dumps(recomendacao.get("customizacao_cv", []), ensure_ascii=False),
                json_result_path,
                json.dumps(result, ensure_ascii=False),
            ),
        )


def save(result: dict, url: str) -> Path:
    out_dir = SCRIPT_DIR / "results"
    out_dir.mkdir(exist_ok=True)

    now = datetime.now()
    timestamp = now.isoformat()
    ts = now.strftime("%Y%m%d_%H%M%S")
    empresa = result.get("vaga", {}).get("empresa", "unknown")
    slug = "".join(c if c.isalnum() else "_" for c in empresa).lower()[:30]
    filename = f"{ts}_{slug}.json"

    payload = {
        "timestamp": timestamp,
        "url": url,
        "fit_score": result.get("fit_score", {}).get("total"),
        "recomendacao": result.get("recomendacao", {}).get("nivel"),
        "analysis": result,
    }
    path = out_dir / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Resultado salvo em: results/{filename}")

    save_to_db(result, url, timestamp, f"results/{filename}")
    print(f"  Registro salvo em: {DB_PATH.name} (tabela job_analyses)")
    return path


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LinkedIn Career Fit Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python linkedin_analyzer.py 'URL'                          # análise completa interativa\n"
            "  python linkedin_analyzer.py 'URL' --skip-calibration       # análise + exibe perguntas, para aqui\n"
            "  python linkedin_analyzer.py --recalibrate results/X.json --answers 3,2,1,3,2  # recalibra JSON existente\n"
        ),
    )
    parser.add_argument("url", nargs="?", help="URL da vaga no LinkedIn")
    parser.add_argument("-f", "--file", help="Arquivo .txt com o texto da vaga")
    parser.add_argument("--no-save", action="store_true", help="Não salvar o resultado em JSON")
    parser.add_argument("--skip-calibration", action="store_true",
                        help="Roda análise, exibe perguntas de calibração e para (use --recalibrate depois)")
    parser.add_argument("--recalibrate", metavar="JSON_FILE",
                        help="Carrega JSON existente e recalibra com --answers (não chama Gemini para análise)")
    parser.add_argument("--answers", metavar="N,N,N,N,N",
                        help="Respostas 0-3 separadas por vírgula para calibração não-interativa")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit(
            "Erro: GEMINI_API_KEY não encontrada.\n"
            "Crie o arquivo .env com:\n  GEMINI_API_KEY=sua_chave_aqui\n"
            "Ou exporte a variável: export GEMINI_API_KEY=sua_chave_aqui"
        )

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    # ── Modo recalibração: carrega JSON existente, não roda análise ──────────
    if args.recalibrate:
        json_path = Path(args.recalibrate)
        if not json_path.exists():
            sys.exit(f"Erro: arquivo '{args.recalibrate}' não encontrado.")
        if not args.answers:
            sys.exit("Erro: --recalibrate requer --answers N,N,N,N,N")

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        result = payload.get("analysis", payload)
        url = payload.get("url", "")

        questions = result.get("vaga", {}).get("calibration_questions", [])
        if not questions:
            sys.exit("Erro: JSON não contém calibration_questions. Gere uma nova análise.")

        try:
            values = [int(v.strip()) for v in args.answers.split(",")]
        except ValueError:
            sys.exit("Erro: --answers deve conter inteiros separados por vírgula (ex: 3,2,1,3,2)")

        if len(values) != len(questions[:5]):
            sys.exit(f"Erro: esperado {len(questions[:5])} respostas, recebido {len(values)}.")

        answers = [
            {
                "skill": q.get("skill", ""),
                "pergunta": q.get("pergunta", q.get("skill", "")),
                "resposta": v,
                "nivel_exigido": q.get("nivel_exigido", ""),
            }
            for q, v in zip(questions[:5], values)
        ]

        print(f"Recalibrando Skills com Gemini ({MODEL})...")
        result = recalibrate_skills(result, answers, client)
        display_calibration_result(result.get("calibration", {}))

        # Atualiza o JSON no disco
        payload["analysis"] = result
        payload["fit_score"] = result.get("fit_score", {}).get("total")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  JSON atualizado: {json_path}")
        return

    # ── Modo análise normal ───────────────────────────────────────────────────
    if not args.url:
        sys.exit("Erro: informe a URL da vaga (ou use --recalibrate para recalibrar um JSON existente).")

    profile = load_file("PROFILE.md")
    pdi     = load_file("PDI.md")

    job_content = get_job_content(args.url, args.file)
    if not job_content.strip():
        sys.exit("Erro: conteúdo da vaga está vazio.")

    print(f"Analisando com Gemini ({MODEL})...")
    result = analyze(args.url, job_content, profile, pdi, client)

    display(result)

    questions = result.get("vaga", {}).get("calibration_questions", [])

    if args.skip_calibration:
        # Salva sem calibração e exibe as perguntas para o usuário responder
        saved_path = None
        if not args.no_save:
            saved_path = save(result, args.url)
        if questions:
            display_questions(questions)
            if saved_path:
                print(f"  Para calibrar: python3 linkedin_analyzer.py --recalibrate {saved_path} --answers N,N,N,N,N\n")
        return

    # Calibração interativa (modo padrão)
    if questions:
        answers = ask_calibration(questions)
        print(f"Recalibrando Skills com Gemini ({MODEL})...")
        result = recalibrate_skills(result, answers, client)
        display_calibration_result(result.get("calibration", {}))
    else:
        print("\n(Perguntas de calibração não disponíveis para esta análise.)\n")

    if not args.no_save:
        save(result, args.url)


if __name__ == "__main__":
    main()
