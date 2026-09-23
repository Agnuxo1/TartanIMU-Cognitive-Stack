"""Compact resource catalog exposed to JEV for routing decisions."""
AGENTS = {
    "luna_scout": "Low-cost retrieval, triage, extraction, and simple synthesis.",
    "luna_coder": "Low-cost code inspection, small edits, and straightforward debugging.",
    "luna_reader": "Low-cost document reading, extraction, and summarization.",
    "luna_opportunity_scout": "Low-cost discovery and triage of current AI awards, project presentations, competitions, and grants.",
    "luna_application_writer": "Low-cost drafting of evidence-backed opportunity narratives, answers, budgets, and checklists.",
    "luna_form_filler": "Low-cost deterministic form preparation from verified project and organization facts.",
    "luna_editor": "Low-cost editorial triage, manuscript operations, metadata, and production checklists.",
    "luna_metadata": "Low-cost catalogue, ISBN, edition, format, and listing reconciliation.",
    "sol_engineer": "Complex coding, debugging, architecture, and technical reasoning.",
    "sol_researcher": "Deep research, source comparison, and technical synthesis.",
    "sol_scientist": "Scientific reasoning with mathematical or domain tools.",
    "sol_grants_researcher": "Complex eligibility, funding, state-aid, impact, budget, and call-document analysis for AI opportunities.",
    "sol_application_reviewer": "Complex review of grant, award, and project-presentation dossiers against official requirements.",
    "sol_rights": "Complex copyright, exclusivity, contract, platform, and distribution analysis.",
    "sol_marketing": "Commercial positioning, outreach, discoverability, and sales strategy for books.",
    "astra_architect": "Exceptional end-to-end reasoning for the hardest novel tasks.",
    "astra_reviewer": "High-stakes final review when maximum capability is justified.",
    "astra_submission_auditor": "Exceptional final audit of eligibility, evidence, forms, attachments, declarations, and submission readiness.",
    "astra_publisher": "Exceptional portfolio-level publishing and multi-channel strategy.",
}
AGENT_MODELS = {
    "luna_scout": "luna", "luna_coder": "luna", "luna_reader": "luna", "luna_opportunity_scout": "luna", "luna_application_writer": "luna", "luna_form_filler": "luna", "luna_editor": "luna", "luna_metadata": "luna",
    "sol_engineer": "sol", "sol_researcher": "sol", "sol_scientist": "sol", "sol_grants_researcher": "sol", "sol_application_reviewer": "sol", "sol_rights": "sol", "sol_marketing": "sol",
    "astra_architect": "astra", "astra_reviewer": "astra", "astra_submission_auditor": "astra", "astra_publisher": "astra",
}
TOOLS = {
    "deterministic_local": "Local Python, arithmetic, parsing, hashing, filtering, and exact operations.",
    "desktop_commander": "Authorized local files, terminal, processes, repositories, and data processing.",
    "exa": "Token-efficient web, code, company, and research search.",
    "context7": "Current programming-library documentation and code examples.",
    "firecrawl": "Targeted website extraction, crawling, mapping, and structured web data.",
    "github": "Repository code, issues, pull requests, commits, and CI context.",
    "scite": "Scientific literature search and citation context.",
    "wolfram": "Exact mathematics, symbolic computation, and curated computational knowledge.",
    "openai_web_search": "Hosted web search available directly to the standalone runtime.",
    "bubok": "Author-panel and public-store publication, catalogue, ISBN, and distribution checks.",
    "lulu": "Bookstore publication, print specifications, cover templates, and nonexclusive terms.",
    "google_books": "Google Books/Play Books partner catalogue and metadata workflow.",
    "gmail": "Read-only mailbox evidence and authorised editorial correspondence.",
    "editorial_workspace": "Local manuscripts, production files, manifests, ledgers, and checkpoints.",
}
PLUGINS = {
    "desktop_commander": "Host-local files, terminal, processes, repositories, and data processing.",
    "exa": "Token-efficient web, code, company, and research search.",
    "context7": "Current programming-library documentation and examples.",
    "firecrawl": "Targeted website extraction, crawling, mapping, and structured web data.",
    "github": "Repository code, issues, pull requests, commits, and CI context.",
    "scite": "Scientific literature search and citation context.",
    "wolfram": "Exact mathematics, symbolic computation, and curated computational knowledge.",
    "openai_web_search": "OpenAI-hosted web search available to the runtime.",
    "bubok": "Bubok author panel and public publishing platform.",
    "lulu": "Lulu publishing and bookstore platform.",
    "google_books": "Google Books/Play Books catalogue platform.",
    "gmail": "Gmail correspondence and evidence source.",
    "editorial_workspace": "Local editorial workspace and production artefacts.",
}
PLUGIN_HOSTS = {name: "chatgpt_host" for name in PLUGINS}
LOCAL_TOOL_EXECUTORS = {"deterministic_local", "openai_web_search"}
SKILLS = {
    "token_compression": "Minimize context and use progressive disclosure.",
    "web_research": "Targeted web research with source verification.",
    "python_debugging": "Python debugging and minimal-change repair workflow.",
    "scientific_research": "Scientific evidence search, comparison, and citation workflow.",
    "repository_analysis": "Repository discovery, symbol filtering, testing, and patch planning.",
    "opportunity_discovery": "Current official-source discovery for AI awards, presentations, competitions, and grants outside Kaggle.",
    "grant_application": "Evidence-backed drafting and field-level completion of grant and award applications.",
    "submission_compliance": "Eligibility, required attachments, declarations, deadlines, and final submission checks.",
    "github_arxiv_evidence": "Build a traceable project evidence chain from GitHub repositories and arXiv papers.",
    "editorial_operations": "Publishing queues, production stages, release checklists, and catalogue operations.",
    "publishing_metadata": "Titles, descriptions, formats, ISBNs, keywords, categories, and platform metadata.",
    "rights_and_contracts": "Rights ownership, exclusivity, licences, ISBN constraints, and distribution gates.",
    "book_marketing": "Author positioning, outreach, discoverability, conversion, and sales pipeline.",
    "general": "No specialized skill required.",
    "typesafe_ai_director": "TypeSafe System One routing, verification, and escalation judgments.",
}
RESEARCH_METHODS = {
    "none": "No research; solve deterministically or from supplied information.",
    "targeted_search": "Search narrowly, then read only the strongest candidates.",
    "progressive_disclosure": "Start with metadata, then progressively load only relevant detail.",
    "deep_research": "Multi-source research with verification and synthesis.",
    "official_call_documents": "Prioritize official call pages, bases, annexes, FAQs, and submission portals.",
    "github_arxiv_first": "Establish project evidence from GitHub and arXiv before drafting an application.",
    "repository_first": "Inspect repository structure and symbols before reading full files.",
    "catalog_reconciliation": "Compare platform records, ISBNs, editions, formats, and local evidence.",
    "contract_review": "Read the relevant contractual clause and compare it with the intended channel plan.",
    "market_scan": "Research comparable books, channels, audiences, and current discoverability opportunities.",
}
WORK_METHODS = {
    "deterministic_first": "Use exact code/tools before any LLM.",
    "single_agent": "Use one appropriately sized agent and stop if confidence is sufficient.",
    "progressive_escalation": "Start cheap and escalate Luna to Sol to Astra only when justified.",
    "tool_first": "Use a specialized tool before invoking a model.",
    "review_loop": "Work, checkpoint with JEV, adjust, and gate final completion.",
    "editorial_preflight": "Verify files, metadata, rights, channel requirements, and cost before publication.",
    "channel_by_channel": "Publish one verified channel at a time and record the public result.",
    "staged_delegation": "Assign bounded subtasks to the cheapest suitable worker and synthesize compact factual outputs.",
    "conditional_thinktank": "Use independent views and an evidence gate only for high-impact uncertainty or disagreement.",
}
DELIBERATION_MODES = {
    "single_worker": "Use one worker and stop when the quality gate is satisfied.",
    "staged_subtasks": "Delegate bounded subtasks to suitable workers and synthesize only compact factual outputs.",
    "two_independent_then_critic": "Run two complementary independent views, then compare them with an evidence gate.",
    "three_role_debate": "Use advocate, skeptic, and verifier only for high-risk rival hypotheses.",
}
CONSENSUS_RULES = {
    "evidence_gate": "Agreement is insufficient; a gatekeeper must compare claims with acceptance criteria and evidence.",
    "majority": "Choose the most common answer even when evidence quality differs.",
    "unanimity": "Continue until every worker agrees.",
    "human_decision": "Defer every final choice to a human.",
}
CONTEXT_POLICIES = {
    "minimal": "Pass only the objective, selected plan, and facts required for the next action.",
    "repository_first": "Pass repository structure and only the files or symbols needed for the next action.",
    "evidence_chain": "Pass compact evidence, source quality, contradictions, and unresolved questions.",
    "handoff_compact": "Pass a bounded factual handoff with acceptance criteria and known failures.",
}
SUCCESS_CRITERIA = {
    "exact_output": "Return the exact requested value or artifact with no unresolved ambiguity.",
    "tested_change": "Implement the requested change and leave relevant tests passing.",
    "evidence_backed": "Support material claims with current, relevant evidence and disclose uncertainty.",
    "complete_workflow": "Satisfy all stated requirements, verify the result, and report remaining limits.",
    "publication_safe": "Publish only after files, metadata, rights, cost, and destination are verified.",
    "application_ready": "Complete the application package, evidence chain, field map, and submission checklist with no invented facts.",
    "rights_verified": "Resolve ownership, exclusivity, licence, and ISBN constraints before release.",
    "multichannel_ready": "Prepare reusable assets and channel-specific metadata without accidental exclusivity.",
    "sales_pipeline_updated": "Leave measurable outreach, listing, and follow-up state recorded.",
}
