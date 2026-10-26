# LLM only and oracle by answerability (validation)

Token F1 (%) from the cached answers; questions without an answer (API error) are left out. Abstention: share of unanswerable questions where the model abstains / share of answerable questions where it abstains.

| System | n | F1 all | F1 answerable | F1 unanswerable | abstain recall / false abstention |
| :--- | ---: | :---: | :---: | :---: | :---: |
| LLM only | 4427 | 15.8 | 15.7 | 18.4 | 17.3 / 8.1 |
| Oracle (gold sections) | 4427 | 35.5 | 36.5 | 15.9 | 15.5 / 2.0 |
