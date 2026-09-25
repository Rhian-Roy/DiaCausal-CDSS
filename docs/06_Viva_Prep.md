# Viva Prep — Questions and Answers

**For:** everyone. Each person owns the questions for their own slides, but everyone should be able to answer all of them.

## The 60-second pitch (Rhian)

> Indian doctors adding a second drug to metformin choose between SGLT2 inhibitors, DPP-4 inhibitors and sulfonylureas. Past records can mislead, because different kinds of patients get different drugs. DiaCausal first removes unsafe options using cited drug-label rules. It then estimates each remaining drug's six-month HbA1c change for this patient with a 95% range, and it says "insufficient evidence" rather than guess. We tested it on an India-calibrated synthetic cohort where the true answers are known, and our benchmark shows how much a naive comparison would mislead. It is decision support only: the doctor decides, every request is logged, and cited guideline explanations arrive in October.

## Four rules for the viva

1. Never invent a number. Say "that is in our results table" and point to it.
2. If you don't know: "We haven't tested that yet — this is how we would test it."
3. Say "synthetic data" whenever you talk about results.
4. Safety first: the doctor decides, safety rules run first, and we refuse to guess.

## Worked numbers to know by heart

| Idea | Numbers |
|---|---|
| Confounding by indication | Naive difference −0.425 vs fair difference −0.15 (about 3× too big) |
| IPW | Two patients with weights 1.25 and 5 turn a naive mean of −0.70 into −0.52 |
| Overlap | Propensities 0.03, 0.55, 0.42 → the first drug gets "insufficient evidence" (0.03 < 0.05) |
| AIPW | Four patients: −0.625 with the correction vs −0.825 from the outcome model alone |
| Units | 1 mmol/mol of HbA1c ≈ 0.09 percentage points |

## Questions and answers

### A. Project and motivation — Pratham

**1. What problem are you solving?**
When metformin alone doesn't control a patient's sugar, the doctor adds a second drug. We compare the three common choices for that specific patient, showing each one's expected 6-month HbA1c change with a range, after unsafe options are removed.

**2. Why does this matter in India?**
India has one of the largest diabetes populations in the world — ICMR-INDIAB estimated about 101 million people with diabetes, 11.4% of adults. Second-line choices are common and cost matters, so we also show the monthly cost.

**3. Why only these three drugs?**
They are the common oral add-on classes after metformin in India. A narrow scope lets us do it properly; insulin and GLP-1 drugs are future work.

**4. Who uses the system?**
A doctor during a consultation. It supports the decision; the doctor always decides.

**5. Is this a medical device? Can hospitals use it now?**
No. It is a research prototype for clinician evaluation — not a marketed medical device and not for unsupervised clinical use. Real use would need validation on real patients, ethics approval and regulatory review.

### B. Causal inference — Rhian

**6. Why causal inference instead of normal machine learning?**
Normal ML predicts what will happen. We need to compare what would happen under each drug for the same patient — a "what if" question. Old records are biased because doctors choose drugs based on the patient, so that bias must be corrected.

**7. What is confounding by indication? Give an example.**
Doctors give certain drugs to certain kinds of patients. In our example the naive comparison says SGLT2i is 0.425 points better, but comparing like with like gives only 0.15 — the naive answer is about three times too big.

**8. What is a propensity score?**
The probability that a patient like this receives each drug, given their details. With three drugs we estimate it with multinomial logistic regression.

**9. What is overlap, and why do you sometimes refuse to answer?**
If almost no similar patients got a drug (propensity below 0.05), there is no fair comparison, so we show "insufficient evidence" instead of guessing.

**10. What is IPW?**
Inverse probability weighting gives more weight to patients who got a drug that was unusual for their type, so each drug group looks like the whole population. Weights of 1.25 and 5 turn a naive mean of −0.70 into −0.52.

**11. What is AIPW, and why is it called doubly robust?**
It combines an outcome model with the propensity weights. It gives the right answer if either model is correct — two chances instead of one — and it gives valid confidence intervals.

**12. What is CATE, and what is a DR-learner?**
CATE is the effect for patients with particular characteristics — a personalised effect. The DR-learner estimates it by learning from the AIPW "pseudo-outcomes", so it keeps the double robustness.

**13. Why cross-fitting?**
We fit the models on one part of the data and predict on another, in rotation. That stops overfitting from making the estimates look better than they are.

**14. How do you know your estimates are correct?**
In our synthetic cohort we know the true effect for every patient, so we measure the error directly: bias, RMSE, interval coverage and PEHE. On real data that is impossible, which is why we test on synthetic data first.

**15. What is PEHE?**
Precision in Estimating Heterogeneous Effects: the root-mean-squared error between estimated and true patient-level effects. Lower is better.

**16. What about confounders you didn't measure?**
That is the main limitation of any observational causal method. We run refutation tests (placebo treatment, random common cause, data subsets) and a sensitivity analysis (E-value), and we state the limitation openly.

**17. Why not causal discovery, like DirectLiNGAM?**
Discovering causal structure from data alone is unreliable for this question. We use a causal graph drawn from medical knowledge; discovery can only be a sanity check.

**18. Why don't you adjust for weight change?**
Weight change happens after the drug starts and is partly caused by it — it is a mediator. Adjusting for it would hide part of the drug's real effect.

### C. Data — Advik

**19. Why synthetic data? Isn't that fake?**
No open Indian dataset records which second-line drug a patient got and their HbA1c six months later. Synthetic data lets us know the true answers and grade our methods; it is calibrated to published Indian figures and every parameter has a cited source.

**20. What does "India-calibrated" mean?**
Prevalence and obesity anchors come from ICMR-INDIAB, BMI cut-offs are Asian-Indian (overweight at 23), and drug-effect directions come from trials and meta-analyses. Each parameter's source and status is recorded in params.yaml.

**21. Why not the Pima Indians diabetes dataset?**
It comes from the Akimel O'odham community in Arizona, USA — not India. It has no treatment variable and uses zeros for missing values, so it cannot answer a treatment question.

**22. How will you use real data later?**
Only with ethics committee approval: de-identified records from the collaborating doctor, then re-check overlap, refit the models, and compare with published trial results.

### D. Implementation and design — Graceton

**23. Why Python, Streamlit and FastAPI?**
Python has the strongest statistics and machine-learning libraries; Streamlit builds a demo interface quickly; FastAPI gives a clean, documented API that a hospital system could call later.

**24. Walk us through one request.**
The doctor enters details, the inputs are checked, safety rules remove unsafe drugs, the propensity and overlap check runs, estimates with 95% ranges (or "insufficient evidence") are produced, the cost is looked up, and the result is shown and logged.

**25. What is in the rules table?**
Each rule has a drug, a condition, an action (exclude or caution), a message, the source document and section, and a verification status. The code reads the table; thresholds are never hard-coded.

**26. How do you test it?**
Automated pytest tests check that rules trigger correctly, propensities add up to 1, AIPW recovers the true effect, abstention works, no dose text ever appears, and the API rejects bad input.

**27. What gets logged?**
Every request: the inputs, the results, the versions of the model, parameters and rules, a request ID and the time — so any output can be traced back.

**28. How would it be deployed?**
As a web application: the FastAPI service plus a web interface on a server. For now it runs on a laptop and can be hosted free on Streamlit Community Cloud for demos.

### E. Safety and ethics — Advik

**29. Can it give wrong advice?**
Any model can be wrong, so we remove unsafe options first, show uncertainty, refuse when data is thin, and leave the decision to the doctor.

**30. Can the AI invent doses?**
No. Doses and thresholds are never generated — they come only from cited tables — and a test fails if any dose text appears in the output.

**31. What about patient privacy?**
We use no real patient data now. Any future real data needs ethics approval and de-identification, and must follow India's Digital Personal Data Protection Act, 2023.

**32. What if the doctor disagrees?**
The doctor decides; the tool offers evidence with reasons and uncertainty. Recording overrides is planned for the next version.

### F. Results and progress — Rhian and Pratham

**33. Is your implementation really 25%?**
More than that: the whole causal half works end to end — data generator, safety rules, estimators, evaluation, demo, API and tests. What remains is RAG, integration, the doctor's review and the paper.

**34. What do your results show?**
Point to the results table: compare the errors of naive, IPW and AIPW against the truth, and the interval coverage. Quote only numbers that are in the table.

**35. What are the limitations?**
Synthetic data; assumed effect sizes; one example drug per class; unmeasured confounding not yet tested on real data; drug prices not yet verified.

**36. What is left to do?**
RAG with citations (1–16 October), integration and full evaluation, the doctor's review, and the final report and IEEE paper by 30 October.

### G. RAG — Graceton

**37. What is RAG, and why do you need it?**
Retrieval-augmented generation: the system first finds relevant passages in approved guidelines, then writes an explanation using only those passages, with citations. It turns our numbers into an explanation doctors can check.

**38. How do you stop the AI from making things up?**
It may use only the retrieved passages, must cite every sentence, and must say "insufficient evidence" when nothing supports an answer. Doses come only from tables.

**39. Which sources will you use?**
Only licence-cleared ones — Indian government and guideline sources and open international guidelines. We check each licence first and never ingest copyrighted textbooks.

**40. Why not just use ChatGPT?**
General chatbots can't guarantee their sources, can invent facts and doses, and don't make patient-specific causal estimates. Ours cites every claim, refuses when unsure, and runs safety rules first.
