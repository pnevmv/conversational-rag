# Demo: answers with their sources

Five answered turns of the validation split, drawn at random (seed 42) among the answered ones; final system with the citation prompt. Sources are the passages and facts cited by the model, shown as document title and section heading; gold = the section holds the grounding span of the reference answer.

## 1. VA, turn 7

> Agent (previous turn): Yes, you can request a Higher-Level Review of an initial claim or Supplemental Claim decision. This option isn't available after a Higher-Level Review or Board decision though.  
> **User:** That's great to hear! Another initial claim or Supplemental Claim decision related issue. Yes, I have no intention of doing so. *It is not possible to ask a question.

**Answer:** You can request a Higher-Level Review of an initial claim or Supplemental Claim decision, but you can’t request it after a Higher-Level Review or Board decision.

**Reference:** *not possible to reply*

**Sources:**

* [1] Insurance claims | Veterans Affairs — Can I request a Higher-Level Review?: not gold

## 2. DMV, turn 5

> Agent (previous turn): In that case you need to surrender your vehicle plates to the DMV immediately.  
> **User:** The other day I also got a letter in the mail saying that my insurance lapsed. I have insurance, so what should I do in that situation?

**Answer:** If you have insurance, follow the instructions in the letter and contact your insurance company or agent about the problem, and ask them to file a notice of coverage with the DMV electronically. You can also submit proof of insurance online or by mail, and the DMV will verify your coverage with your insurance company.

**Reference:** Simply follow the instructions in the letter and contact your company or agent about the problem. Ask your company to file a notice of coverage with the DMV electronically.

**Sources:**

* [1] Respond to DMV insurance letters and orders — I received a Letter that states my insurance lapsed. What can I do?: gold
* [2] Provide proof of insurance — Provide proof of insurance [1]: not gold
* [F7] Insurance lapses — What is an insurance lapse in New York State?: not gold
* [11] (not a valid passage or fact number)
* [F11] Suspensions and revocations — How to check if your license is suspended or revoked: not gold

## 3. STUDENTAID, turn 7

> Agent (previous turn): The consolidation usually increases the period of time you have to repay your loans.  
> **User:** I see... But anyhow, how do I apply for a consolidation of the loan?

**Answer:** To apply for a Direct Consolidation Loan, you must log in to complete and submit the Federal Direct Consolidation Loan Application and Promissory Note online, and if you need technical assistance you can contact the Student Loan Support Center at 1-800-557-7394. If you have already submitted your application, you should contact the servicer for your new Direct Consolidation Loan.

**Reference:** You just need to apply for it, be online or in paper.

**Sources:**

* [4] Student Loan Consolidation | Federal Student Aid — Whom do I contact if I have questions about consolidation?: not gold

## 4. DMV, turn 7

> Agent (previous turn): After selling a vehicle, you don't have to remove a lienholder from the title certificate, you give the original title and lien release to the buyer  
> **User:** I have another question about the Graduated License Law and Restrictions for Drivers under 18, what junior driver license classes are restricted under it?

**Answer:** Under the Graduated License Law, if you are under 18 and have a junior learner permit or a junior driver license class DJ, MJ, or DJMJ, you are subject to restrictions. If you do not comply, your junior learner permit or junior driver license could be suspended or revoked for 60 days.

**Reference:** In addition to a junior learner permit, junior driver license classes DJ, MJ, and DJMJ are restricted under the Graduated License Law.

**Sources:**

* [1] The Graduated License Law and Restrictions for Drivers under 18 — The Graduated License Law and Restrictions for Drivers under 18[1]: gold

## 5. STUDENTAID, turn 9

> Agent (previous turn): Do you believe you are eligible for the military deferment?  
> **User:** Yes, I believe I am.

**Answer:** Yes, you may be eligible for a Military Service and Post-Active Duty Student Deferment if you’re on active duty in connection with a war, military operation, or national emergency, or if you’ve completed qualifying active duty service and any applicable grace period. You must complete the Military Service and Post-Active Duty Student Deferment Request and submit it to your loan servicer.

**Reference:** Are you on active duty military service ?

**Sources:**

* [3] Student Loan Deferment | Federal Student Aid — Military Service and Post-Active Duty Student Deferment: gold
* [F27] Student Loan Deferment | Federal Student Aid — Request a Deferment: not gold
