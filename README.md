# PROMETEUS — Lightweight Agent-Based AI for Edge Devices

> An experimental AI system built on a dynamic knowledge graph and specialized micro-agents.  
> Designed to run offline on low-resource hardware — no GPU, no cloud, no retraining.

---

## The Problem

Modern AI requires massive resources:

| System | RAM | GPU | Offline? |
|--------|-----|-----|----------|
| GPT-4 | ~80GB | $10,000+ | ❌ |
| LLaMA 7B | ~14GB | Required | ⚠️ |
| **PROMETEUS** | ~20MB (target) | None | ✅ |

1 billion people use feature phones without internet access.  
For them, cloud AI will never be an option.  
This is an architectural problem, not a hardware problem.

---

## What PROMETEUS Is

Not a language model. Not a compressed transformer.  
A different approach entirely:

- **Knowledge graph** (SQLite) instead of weight matrices
- **Micro-agents** with threshold activation instead of attention layers
- **Online learning** — graph enriches itself recursively from new input
- **Internet fallback** — fetches and stores new concepts when online
- **Offline fallback** — asks user to explain unknown concepts when offline

---

## Current Status

This is an early-stage research prototype. Honest assessment:

| Component | Status |
|-----------|--------|
| Knowledge base + SQLite graph | ✅ Working |
| Weighted edges + threshold activation | ✅ Working |
| Internet fallback for unknown concepts | ✅ Working |
| Recursive graph self-enrichment | ✅ Working |
| Natural language understanding (NLP) | 🔧 In progress |
| agent_analogy (relational reasoning) | 📋 Planned |
| Benchmark measurements | 📋 Planned |

Simple structured commands work. Natural language parsing is the next milestone.

---

## Architecture

```
User Input
    ↓
agent_language       — tokenize, detect intent
    ↓
Graph lookup         — find matching nodes in SQLite
    ↓
Agent activation     — threshold-based, only relevant agents fire
    ↓
agent_analogy        — structural similarity across domains (planned)
    ↓
Response assembly
    ↓
agent_pattern        — reinforce connections, spawn new agents
```

### Three Layers

**Layer 1 — Core reflexes** (hardcoded at startup)
- `agent_language` — tokenization, structure detection
- `agent_memory` — current dialogue context
- `agent_pattern` — recurring pattern detection
- `agent_spawn` — creates new agents from patterns
- `agent_analogy` — cross-domain structural similarity

**Layer 2 — Knowledge graph** (grows dynamically)
- Nodes = concepts with properties
- Edges = typed relations (IS_A, HAS, RELATED_TO)
- Weights = connection strength 0.0 → 1.0

**Layer 3 — Specialized agents** (created on demand)
- Domain agents: medicine, weather, math, etc.
- Created from combinations of core agents
- Sleep when unused > N days

---

## Learning Mechanism

No backpropagation. No retraining. Local only.

- **Hebbian learning** — agents that fire together strengthen their connection
- **Chunking** — pattern repeated 3+ times → new agent spawned
- **Forgetting** — strength < 0.2 → agent sleeps
- **Feedback** — user says "wrong" → connections weaken
- **Analogy** — structural match → new generalized rule (planned)

---

## Why This Matters

```
Transformers:  large model → quantization → distillation → edge
PROMETEUS:     graph + agents → edge-first → scale up
```

Every major lab compresses big models down.  
This project asks: what if you design for the edge from the start?

Target hardware: feature phones, Raspberry Pi, Arduino-class devices, smartwatches.

---

## Benchmark

> Tested on Raspberry Pi 4 (4GB RAM) as reference edge device.  
> PROMETEUS results will be updated as the prototype matures.

### RAM Usage

| System | RAM at load |
|--------|-------------|
| LLaMA 7B (llama.cpp) | ~4,000 MB |
| LLaMA 3B (llama.cpp) | ~2,000 MB |
| Phi-2 2.7B | ~1,600 MB |
| **PROMETEUS** | **TBD** |

### Response Time on Raspberry Pi 4

| System | Avg response time |
|--------|-------------------|
| LLaMA 7B | 45–120 sec |
| LLaMA 3B | 15–40 sec |
| Phi-2 | 10–25 sec |
| **PROMETEUS** | **TBD** |

### Hardware Compatibility

| Device | LLaMA 7B | LLaMA 3B | PROMETEUS |
|--------|----------|----------|-----------|
| Raspberry Pi 4 (4GB) | ⚠️ Slow | ✅ | ✅ |
| Raspberry Pi Zero (512MB) | ❌ | ❌ | ✅ |
| Android 2GB RAM | ❌ | ❌ | ✅ |
| Feature phone | ❌ | ❌ | ✅ |
| Arduino-class MCU | ❌ | ❌ | 🔧 Planned |

> PROMETEUS does not compete with LLMs in general dialogue.  
> Its advantage is narrow-domain accuracy on hardware where LLMs cannot run at all.

*Full benchmark methodology and raw numbers coming in Month 2–3.*

---

## Roadmap

| Phase | Timeline | Goal |
|-------|----------|------|
| ✅ Core graph + agents | Done | SQLite graph, weighted activation, fallbacks |
| 🔧 NLP layer | Month 1-2 | pymorphy3 + intent detection, natural language input |
| 📋 Benchmark | Month 2-3 | RAM / speed / accuracy on Raspberry Pi |
| 📋 agent_analogy | Month 3-6 | Relational reasoning, cross-domain generalization |
| 📋 Vertical product | Month 4-6 | Offline medical assistant or IoT SDK |
| 📋 Publication | Month 6-12 | Academic paper, open source core |

---

## Target Markets

- **Offline medicine** — villages, disaster zones, no connectivity
- **IoT / smart devices** — microcontrollers, no GPU, $500B market by 2030
- **Education in developing countries** — 1B+ users on feature phones
- **Industrial edge devices** — offline, real-time, $200B market by 2028
- **Private personal assistants** — no cloud, no data leaks

---

## Looking For

- **ML engineer** who believes in alternative architectures
- **NLP specialist** for lightweight Russian/multilingual parsing
- **Embedded developer** for low-level optimization
- **Researchers** interested in relational reasoning without neural nets

If this direction interests you — open an issue or reach out directly.

---

## Getting Started

```bash
git clone https://github.com/YOUR_USERNAME/prometeus
cd prometeus
pip install -r requirements.txt
python main.py
```

*Full setup instructions coming as the prototype stabilizes.*

---

## Commercial Use

Free for research, education, and non-commercial use.  
Commercial licensing available — contact to discuss terms.

📧 **your@email.com**

---

## License

Licensed under Apache 2.0 with Commons Clause.  
Free for research and non-commercial use.  
Commercial use requires a separate written agreement.

See [LICENSE](./LICENSE) for full terms.

---

## Concept

> Transformers solved language understanding through scale.  
> PROMETEUS explores solving it through structure.  
> The brain works not because it is large — but because it is organized correctly.

PROMETEUS · Conceptual prototype · 2025  
*Not AGI. Not a transformer replacement. An honest experiment in edge-first AI architecture.*
