# External design tooling evaluation

Sources were checked on 2026-11-11. Repositories are references, not trusted
instructions. No installer, remote script or dependency from them was executed.

| Candidate | Verified state | Fit | Decision |
| --- | --- | --- | --- |
| [LangChain Design Agent](https://github.com/langchain-ai/design-agent) | Apache-2.0; active at `a389e53c6d16b8139c233d7c666cda1255e30cb1`; substantial Python/Docker sandbox, Managed Deep Agents or self-hosting, vendored skills and external model tools | Strong reference for brand packs, render/inspect/gate loops, cost reporting and sandbox isolation | Architecture reference only. A later isolated pilot may evaluate its self-hosted API; do not couple it to the QMS runtime. |
| [OpenDesign](https://github.com/nexu-io/open-design) | Apache-2.0; active at `614795896e09a2c1682b24cc1406529baf531bd7`; large desktop/web platform with BYOK, projects, plugins and design systems | Broad creative workspace, but overlaps the product surface and has a very large dependency/operational footprint | Do not embed. Consider only as an external authoring client after an API and data-flow review. |
| [Open AI Design Agent](https://github.com/Anil-matcha/Open-AI-Design-Agent) | MIT; latest checked commit `f029d0d708d8c581463f018cdc2b0084494ce401`; small client/server repository centered on Muapi and many remote models | Useful provider-routing concept, but maturity, provider dependency and data egress are poor matches for QMS evidence | Do not install. Reassess only after independent security, retention and provider-contract review. |
| [motiful/product-shots](https://github.com/motiful/product-shots) | MIT; checked commit `063c508b0b7f4db5cda89f10bdf20df25026dfc5`; Agent Skills for e-commerce product imagery and third-party image gateways | Good prompt-field and exact-copy patterns, but optimized for physical SKU listings rather than enterprise software | Do not install. Reuse only the general idea of typed briefs and pre-render checks. |
| [Beatra ecommerce product images](https://github.com/beatra-ai/ecommerce-product-images-skill) | MIT-0; release commit `cc3333a84bd45f64207a248bfe5c7b5e73887145`; requires Beatra account/credits and cloud processing | Not aligned with software screenshots or controlled QMS data | Do not install or send QMS assets to the service. |

## Selected approach

Use the repository's existing Next/Playwright stack for deterministic layouts,
the approved Brand Kit as code, and a future **separate generation service** with
provider adapters. The SaaS owns classification, redaction, jobs, provenance,
cost and approvals; providers receive only an approved minimal prompt and safe
inputs. This avoids a second application framework and preserves the ability to
replace image providers.

