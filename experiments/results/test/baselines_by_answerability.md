# LLM only and oracle by answerability (test)

Token F1 (%) from the cached answers; questions without an answer (API error) are left out. Abstention: share of unanswerable questions where the model abstains / share of answerable questions where it abstains.

| System | n | F1 all | F1 answerable | F1 unanswerable | abstain recall / false abstention |
| :--- | ---: | :---: | :---: | :---: | :---: |
| LLM only | 4334 | 15.1 | 15.0 | 15.7 | 14.5 / 11.8 |
| Oracle (gold sections) | 4335 | 34.2 | 35.1 | 19.6 | 18.7 / 2.4 |
