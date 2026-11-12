# Graph Report - gerador-de-audio  (2026-10-31)

## Corpus Check
- Corpus is ~2,882 words - fits in a single context window. You may not need a graph.

## Summary
- 70 nodes · 105 edges · 7 communities (2 shown, 5 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 4 edges (avg confidence: 0.88)
- Token cost: 1,200 input · 450 output

## Community Hubs (Navigation)
- Audio Processing & Text Extraction
- Core Application & Framework Setup
- Job Log Management & SSE Streaming
- API Download & Status Endpoints
- Book Upload & Task Dispatch
- Maintenance & File Cleanup
- Project Documentation & Specifications

## God Nodes (most connected - your core abstractions)
1. `JobLogManager` - 11 edges
2. `executar_processamento_livro()` - 11 edges
3. `processar_livro()` - 10 edges
4. `gerar_parte_sincronizada()` - 7 edges
5. `limpar_arquivos_antigos()` - 5 edges
6. `extrair_texto_pdf()` - 5 edges
7. `extrair_texto_docx()` - 5 edges
8. `alinhar_pontuacao_e_paragrafos()` - 4 edges
9. `status_job()` - 4 edges
10. `agrupar_em_lotes()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `Dependências do Projeto` --conceptually_related_to--> `API de Geração de Audiolivro e Sincronização`  [INFERRED]
  requirements.txt → README.md

## Import Cycles
- None detected.

## Communities (7 total, 5 thin omitted)

### Community 0 - "Audio Processing & Text Extraction"
Cohesion: 0.19
Nodes (6): agrupar_em_lotes(), alinhar_pontuacao_e_paragrafos(), executar_processamento_livro(), extrair_texto_docx(), extrair_texto_pdf(), gerar_parte_sincronizada()

### Community 3 - "API Download & Status Endpoints"
Cohesion: 0.15
Nodes (6): baixar_audio(), baixar_mapa(), listar_vozes(), root(), status_job(), stream_logs_job()

## Knowledge Gaps
- **4 isolated node(s):** `Túnel Server-Sent Events (SSE)`, `Sincronização de Texto e Áudio (Karaokê)`, `Dependências do Projeto`, `Edge-TTS Neural Voice Engine`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 36 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `JobLogManager` connect `Job Log Management & SSE Streaming` to `Core Application & Framework Setup`?**
  _High betweenness centrality (0.339) - this node is a cross-community bridge._
- **What connects `Túnel Server-Sent Events (SSE)`, `Sincronização de Texto e Áudio (Karaokê)`, `Dependências do Projeto` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Core Application & Framework Setup` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
- **Why does `processar_livro()` connect `Book Upload & Task Dispatch` to `Audio Processing & Text Extraction`, `Core Application & Framework Setup`, `Maintenance & File Cleanup`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Why does `status_job()` connect `API Download & Status Endpoints` to `Core Application & Framework Setup`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._