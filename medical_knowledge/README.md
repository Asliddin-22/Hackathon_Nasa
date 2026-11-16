# Reviewed reference corpus

Reviewed on November 15, 2026. This corpus contains selected source text, not complete publications. Whitespace is normalized; the MedlinePlus topic summaries also normalize list punctuation. No generated medical facts are labeled as source text. Images, videos, logos, third-party contributions, treatment instructions, and linked external documents are excluded. Use is educational and implies no NIH/NASA endorsement or clinical approval.

Every source file records its original URL, publisher, system, category, source update date when verified (otherwise null), review date, version, section headings, SHA-256 over the normalized sections, scope, attribution, rights status, and permission-policy URL. Ingestion rejects missing permission review, unapproved domains, bad IDs, and checksum mismatch before changing the database. Source/chunk IDs are stable across idempotent re-ingestion.

| Source document | Category / system | Indexed passages | Permission policy |
| --- | --- | --- | --- |
| [First Aid — selected Summary](https://medlineplus.gov/firstaid.html) | fundamentals / emergency_support | 2 | [Reviewed text policy](https://medlineplus.gov/about/using/usingcontent/) |
| [Medical Operations — selected context](https://www.nasa.gov/reference/6-0-medical-operations/) | space_medicine / emergency_support | 2 | [Reviewed text policy](https://www.nasa.gov/nasa-brand-center/images-and-media/) |
| [Dehydration — Summary](https://medlineplus.gov/dehydration.html) | fundamentals / kidney | 3 | [Reviewed text policy](https://medlineplus.gov/about/using/usingcontent/) |
| [Dizziness and Vertigo — Summary](https://medlineplus.gov/dizzinessandvertigo.html) | fundamentals / balance | 3 | [Reviewed text policy](https://medlineplus.gov/about/using/usingcontent/) |
| [How the Eyes Work](https://www.nei.nih.gov/eye-health-information/healthy-vision/how-eyes-work) | fundamentals / vision | 2 | [Reviewed text policy](https://www.nei.nih.gov/web-policies/copyright-policy) |
| [How the Heart Works — How the Heart Beats](https://www.nhlbi.nih.gov/health/heart/heart-beats) | fundamentals / cardiovascular | 4 | [Reviewed text policy](https://www.nhlbi.nih.gov/about/contact/trademark-branding-and-logo) |
| [How the Heart Works — The Heart](https://www.nhlbi.nih.gov/health/heart) | fundamentals / cardiovascular | 3 | [Reviewed text policy](https://www.nhlbi.nih.gov/about/contact/trademark-branding-and-logo) |
| [What Is Bone?](https://www.niams.nih.gov/health-topics/what-bone) | fundamentals / bone | 2 | [Reviewed text policy](https://www.niams.nih.gov/disclaimer) |
| [Health Lesson: Learning About Muscles](https://www.niams.nih.gov/health-topics/educational-resources/health-lesson-learning-about-muscles) | fundamentals / muscle | 3 | [Reviewed text policy](https://www.niams.nih.gov/disclaimer) |
| [Balance Disorders](https://www.nidcd.nih.gov/health/balance-disorders) | fundamentals / balance | 2 | [Reviewed text policy](https://www.nidcd.nih.gov/policies) |
| [Your Kidneys & How They Work](https://www.niddk.nih.gov/health-information/kidney-disease/kidneys-how-they-work) | fundamentals / kidney | 2 | [Reviewed text policy](https://www.niddk.nih.gov/copyright) |
| [Cardiovascular and Vision — Cardiovascular Concerns](https://www.nasa.gov/directorates/esdmd/hhp/cardiovascular-and-vision/) | space_medicine / cardiovascular | 1 | [Reviewed text policy](https://www.nasa.gov/nasa-brand-center/images-and-media/) |
| [The Human Body in Space — Gravity Fields](https://www.nasa.gov/humans-in-space/the-human-body-in-space/) | space_medicine / multisystem | 3 | [Reviewed text policy](https://www.nasa.gov/nasa-brand-center/images-and-media/) |
| [Risk of Spaceflight Associated Neuro-ocular Syndrome (SANS)](https://www.nasa.gov/reference/risk-of-spaceflight-associated-neuro-ocular-syndrome-sans/) | space_medicine / vision | 1 | [Reviewed text policy](https://www.nasa.gov/nasa-brand-center/images-and-media/) |
| [OCHMO-MTB-003 Urinary Health](https://www.nasa.gov/ochmo-mtb-003-urinary-health-2/) | space_medicine / kidney | 1 | [Reviewed text policy](https://www.nasa.gov/nasa-brand-center/images-and-media/) |

Permission review:

- NHLBI: its policy permits use of public-domain text with the requested source attribution; third-party medical animations and logos were excluded.
- NIAMS: its disclaimer explicitly permits copying its public-domain text; purchased images were excluded. The muscle lesson is an introductory educational source, not clinical evidence for adult diagnostic decisions.
- NIDCD and NEI: public-domain text unless otherwise marked, with attribution; media and third-party material were excluded.
- NIDDK: unchanged informational text with attribution, excluding third-party material and logos; content is reference information, not institute-endorsed advice or referral.
- MedlinePlus: only its public-domain Health Topic Summary sections. The A.D.A.M. encyclopedia, drug monographs, externally linked content, images, and treatment sections were not ingested. [NLM policy](https://medlineplus.gov/about/using/usingcontent/).
- NASA: NASA-authored informational/research-context text with attribution and no endorsement. [NASA use guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/). No imagery, third-party material, or treatment sections were ingested.
- NCBI Bookshelf: discovered as an expansion candidate but **not indexed**. Its [copyright notice](https://www.ncbi.nlm.nih.gov/sites/books/about/copyright/) requires per-work rights checking and approved automated retrieval channels. Free access is not a blanket ingestion license.

The older `sources.json` and demo protocol remain available to the original trend-explanation workflow. The new reference corpus has its own per-document provenance and is indexed locally with SQLite FTS5. No model training or remote embedding service is used.

The current inventory is **15 documents / 34 passages**. First Aid supplies basic assistance/training context; Medical Operations supplies onboard-care and delayed-communication context. Neither is labeled as a mission-approved clinical treatment protocol. The emergency overlay can load these checked-in references even if FTS indexing is unavailable.
