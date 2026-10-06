# Sheet 4: v2 triples with the gold facts of their section

For each section with v2 triples: the text, the gold facts (correct v1 triples `t####` and missing facts `m##`), and the v2 triples in `4_triples_v2.csv` with their label and gold id.

## Register a leased vehicle#1_0::11

> Summary of what you need a certified copy of the title certificate , original Manufacturers Statement of Origin MSO or Manufacturer's Certificate of Origin MCO 1 current NY State Insurance ID card auto liability insurance 2 NY State driver license , permit , non - driver ID , or other proof of identity 3 authorization from the leasing company to register the vehicle in New York, which consists of all these things a letter from the leasing company that gives you permission to register the vehicle in NY State a power of attorney from the leasing company that authorizes you to register the vehicle in NY State the signature of a leasing company officer in box 3 on the Vehicle Registration / Title Application PDF [3] MV-82 or on the Registration Authorization PDF [4] MV-95 proof of sales tax payment, sales tax exemption, or purchase price see below for instructions for to show proof

Gold facts:
- `t0001` authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> letter from the leasing company that gives you permission to register the vehicle in NY State (Document)
- `t0002` authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> power of attorney from the leasing company that authorizes you to register the vehicle in NY State (Document)
- `t0003` authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> Vehicle Registration / Title Application PDF (MV-82) (Document)
- `t0004` authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> Registration Authorization PDF (MV-95) (Document)
- `m01` register a leased vehicle (Service) -REQUIRES-> certified copy of the title certificate (Document)
- `m02` register a leased vehicle (Service) -REQUIRES-> original Manufacturers Statement of Origin (MSO) or Manufacturer's Certificate of Origin (MCO) (Document)
- `m03` register a leased vehicle (Service) -REQUIRES-> current NY State Insurance ID card (Document)
- `m04` register a leased vehicle (Service) -REQUIRES-> proof of identity (Requirement)
- `m05` register a leased vehicle (Service) -REQUIRES-> authorization from the leasing company to register the vehicle in New York (Requirement)
- `m06` register a leased vehicle (Service) -REQUIRES-> proof of sales tax payment, sales tax exemption, or purchase price (Requirement)
- `m07` register a leased vehicle (Service) -REQUIRES-> signature of a leasing company officer in box 3 on the Vehicle Registration / Title Application PDF (MV-82) or Registration Authorization PDF (MV-95) (Requirement)

v2 triples:
- `annotation_v2_0001` [correct, m01] register a leased vehicle (Service) -REQUIRES-> certified copy of the title certificate (Document)
- `annotation_v2_0002` [correct, m02] register a leased vehicle (Service) -REQUIRES-> original Manufacturers Statement of Origin (MSO) (Document)
- `annotation_v2_0003` [correct, m02] register a leased vehicle (Service) -REQUIRES-> Manufacturer's Certificate of Origin (MCO) (Document)
- `annotation_v2_0004` [correct, m03] register a leased vehicle (Service) -REQUIRES-> current NY State Insurance ID card (Document)
- `annotation_v2_0005` [correct] register a leased vehicle (Service) -REQUIRES-> auto liability insurance (Requirement)
- `annotation_v2_0006` [correct] register a leased vehicle (Service) -REQUIRES-> NY State driver license (Document)
- `annotation_v2_0007` [correct, m05] register a leased vehicle (Service) -REQUIRES-> authorization from the leasing company to register the vehicle in New York (Requirement)
- `annotation_v2_0008` [correct, t0001] authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> letter from the leasing company that gives you permission to register the vehicle in NY State (Document)
- `annotation_v2_0009` [correct, t0002] authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> power of attorney from the leasing company that authorizes you to register the vehicle in NY State (Document)
- `annotation_v2_0010` [correct, t0003] authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> Vehicle Registration / Title Application PDF (MV-82) (Document)
- `annotation_v2_0011` [correct, t0004] authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> Registration Authorization PDF (MV-95) (Document)
- `annotation_v2_0012` [correct, m06] register a leased vehicle (Service) -REQUIRES-> proof of sales tax payment, sales tax exemption, or purchase price (Requirement)

## Register a leased vehicle#1_0::2

> How to register a leased vehicle If you leased the vehicle from a dealer in New York State , the dealer normally registers the vehicle for you by providing all your proofs and your registration application to the DMV. In this case , you don t need to do anything more. If the dealer does not provide the proofs to the DMV , you must register the vehicle at a DMV office. Please complete the Document Guide to make sure you bring the correct documents with you. Find your proofs [2 ]

Gold facts:
- `t0006` register a leased vehicle (Service) -REQUIRES-> proofs (Document)
- `t0007` register a leased vehicle (Service) -REQUIRES-> registration application (Document)
- `t0011` register a leased vehicle (Service) -AVAILABLE_AT-> DMV office (ContactPoint)
- `t0012` register a leased vehicle (Service) -REQUIRES-> Document Guide (Document)
- `m08` register a leased vehicle (Service) -PROVIDED_BY-> dealer (Organization)

v2 triples:
- `annotation_v2_0013` [incorrect] register a leased vehicle (Service) -PROVIDED_BY-> DMV (Organization)
- `annotation_v2_0014` [correct, t0006] register a leased vehicle (Service) -REQUIRES-> proofs (Document)
- `annotation_v2_0015` [correct, t0007] register a leased vehicle (Service) -REQUIRES-> registration application (Document)
- `annotation_v2_0016` [incorrect] register a leased vehicle (Service) -REQUIRES-> correct documents (Requirement)
- `annotation_v2_0017` [correct, t0011] register a leased vehicle (Service) -AVAILABLE_AT-> DMV office (ContactPoint)

## Register a leased vehicle#1_0::25

> Proof of sales tax payment If you paid New York State sales tax to the leasing company or dealer on the total amount of all your lease payments , provide your lease agreement that indicates that you paid the NY State sales tax, and complete the Claim for Sales Tax Exemption {Sales Tax Form} PDF [5] at NY State Department of Tax and Finance DTF-803. If you did not pay New York State sales tax to the leasing company or dealer on all of your lease payments , provide your lease agreement , and complete Statement of Transaction {Sales Tax Form} PDF [6] at NY State Department of Tax and Finance DTF-802. You must pay NY State sales tax at the DMV office on any lease payments if the leasing company or dealer did not collect the sales tax. The sales tax is collected in one complete payment at the time of registration. If you made one payment to another state for the total amount of sales tax, complete Claim for Credit of Sales Tax Paid to Another State {Sales Tax Form} PDF [7] at NY State Department of Tax and Finance DTF-804 to request credit for the tax you paid, and then pay the balance of any NY State sales tax. This process can reduce the amount of your NY State sales tax if NY State and the other state have an agreement about sales tax. Not all states have an agreement with New York. See DFT-804 page 2. If you made monthly sales tax payments in another state, complete form Statement of Transaction {Sales Tax Form} PDF [6] at NY State Department of Tax and Finance DTF-802, and pay the total amount of NY State sales tax in one payment for all the lease payments that remain. See also Change name on title after lease buyout [8]. You will not receive the original title certificate as proof of ownership. The leasing company is the owner and holds the title certificate, which displays their name. Your insurance company will: 1) give you 2 barcoded original NY State Insurance ID cards (see a sample [9]) or provide you with access to your digital electronic NY State Insurance ID Card 2) send an electronic notice of insurance coverage to the DMV (your insurance agent or broker cannot file this notice) Your NY State Insurance ID cards and the electronic notice together verify your coverage. We need both. You must register your vehicle within 180 days of the effective date on your Insurance ID Card. Bring one copy or form of your Insurance ID Card with you. The DMV office will keep the paper card. Keep the other paper card with the vehicle as your proof of insurance. Anyone operating your vehicle must be able to provide proof of insurance. Learn more about NY State Insurance Requirements [10]. You must be at least 16 years old except for ATV registrations. You can use a NY State Driver License, Learner Permit, or Non - Driver ID card that is current or not expired for more than 2 years as proof of both identity and age . If you don t have one of these, see other kinds of proof [11] you can use.

Gold facts:
- `t0013` Proof of sales tax payment (Requirement) -REQUIRES-> lease agreement (Document)
- `t0014` Proof of sales tax payment (Requirement) -REQUIRES-> Claim for Sales Tax Exemption (Document)
- `t0015` Proof of sales tax payment (Requirement) -REQUIRES-> Statement of Transaction (Document)
- `t0016` Proof of sales tax payment (Requirement) -REQUIRES-> Claim for Credit of Sales Tax Paid to Another State (Document)
- `t0017` Claim for Sales Tax Exemption (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- `t0018` Statement of Transaction (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- `t0019` Claim for Credit of Sales Tax Paid to Another State (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- `t0021` register your vehicle (Service) -HAS_TIME_LIMIT-> 180 days (TimeLimit)
- `t0023` register your vehicle (Service) -REQUIRES-> proof of insurance (Requirement)
- `t0024` register your vehicle (Service) -REQUIRES-> at least 16 years old (Requirement)
- `m09` register your vehicle (Service) -REQUIRES-> NY State Insurance ID cards (Document)
- `m10` register your vehicle (Service) -REQUIRES-> electronic notice of insurance coverage (Document)
- `m11` NY State Insurance ID cards (Document) -PROVIDED_BY-> your insurance company (Organization)
- `m12` electronic notice of insurance coverage (Document) -PROVIDED_BY-> your insurance company (Organization)
- `m13` anyone operating your vehicle (Role) -REQUIRES-> proof of insurance (Requirement)
- `m14` NY State Driver License (Document) -ALTERNATIVE_TO-> Learner Permit (Document)
- `m15` NY State Driver License (Document) -ALTERNATIVE_TO-> Non-Driver ID card (Document)
- `m16` Learner Permit (Document) -ALTERNATIVE_TO-> Non-Driver ID card (Document)

v2 triples:
- `annotation_v2_0018` [incorrect] Proof of sales tax payment (Service) -REQUIRES-> lease agreement (Document)
- `annotation_v2_0019` [incorrect] Proof of sales tax payment (Service) -REQUIRES-> Claim for Sales Tax Exemption {Sales Tax Form} PDF (Document)
- `annotation_v2_0020` [incorrect] Proof of sales tax payment (Service) -REQUIRES-> Statement of Transaction {Sales Tax Form} PDF (Document)
- `annotation_v2_0021` [incorrect] Proof of sales tax payment (Service) -REQUIRES-> Claim for Credit of Sales Tax Paid to Another State {Sales Tax Form} PDF (Document)
- `annotation_v2_0022` [correct, t0017] Claim for Sales Tax Exemption {Sales Tax Form} PDF (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- `annotation_v2_0023` [correct, t0018] Statement of Transaction {Sales Tax Form} PDF (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- `annotation_v2_0024` [correct, t0019] Claim for Credit of Sales Tax Paid to Another State {Sales Tax Form} PDF (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- `annotation_v2_0025` [incorrect] Proof of sales tax payment (Service) -LEADS_TO-> sales tax collected in one complete payment at the time of registration (Outcome)
- `annotation_v2_0026` [incorrect] Claim for Sales Tax Exemption {Sales Tax Form} PDF (Document) -ALTERNATIVE_TO-> Statement of Transaction {Sales Tax Form} PDF (Document)
- `annotation_v2_0027` [incorrect] Claim for Credit of Sales Tax Paid to Another State {Sales Tax Form} PDF (Document) -ALTERNATIVE_TO-> Claim for Sales Tax Exemption {Sales Tax Form} PDF (Document)
- `annotation_v2_0028` [incorrect] Claim for Credit of Sales Tax Paid to Another State {Sales Tax Form} PDF (Document) -ALTERNATIVE_TO-> Statement of Transaction {Sales Tax Form} PDF (Document)
- `annotation_v2_0029` [incorrect] Statement of Transaction {Sales Tax Form} PDF (Document) -PROVIDED_BY-> NY State Department of Tax and Finance DTF-802 (Organization)
- `annotation_v2_0030` [incorrect] register your vehicle within 180 days of the effective date on your Insurance ID Card (Service) -HAS_TIME_LIMIT-> within 180 days of the effective date on your Insurance ID Card (TimeLimit)
- `annotation_v2_0031` [incorrect] register your vehicle within 180 days of the effective date on your Insurance ID Card (Service) -REQUIRES-> your NY State Insurance ID cards and the electronic notice (Requirement)
- `annotation_v2_0032` [incorrect] register your vehicle within 180 days of the effective date on your Insurance ID Card (Service) -REQUIRES-> one copy or form of your Insurance ID Card (Document)
- `annotation_v2_0033` [incorrect] register your vehicle within 180 days of the effective date on your Insurance ID Card (Service) -REQUIRES-> Anyone operating your vehicle must be able to provide proof of insurance (Requirement)
- `annotation_v2_0034` [incorrect] register your vehicle within 180 days of the effective date on your Insurance ID Card (Service) -REQUIRES-> at least 16 years old except for ATV registrations (Requirement)
- `annotation_v2_0035` [correct, m14] Learner Permit (Document) -ALTERNATIVE_TO-> NY State Driver License (Document)
- `annotation_v2_0036` [correct, m15] Non - Driver ID card (Document) -ALTERNATIVE_TO-> NY State Driver License (Document)
- `annotation_v2_0037` [correct, m16] Learner Permit (Document) -ALTERNATIVE_TO-> Non - Driver ID card (Document)
- `annotation_v2_0038` [incorrect] NY State Driver License (Document) -REQUIRES-> current or not expired for more than 2 years (Requirement)
- `annotation_v2_0039` [incorrect] Learner Permit (Document) -REQUIRES-> current or not expired for more than 2 years (Requirement)
- `annotation_v2_0040` [incorrect] Non - Driver ID card (Document) -REQUIRES-> current or not expired for more than 2 years (Requirement)
- `annotation_v2_0041` [incorrect] NY State Driver License (Document) -REQUIRES-> proof of both identity and age (Requirement)
- `annotation_v2_0042` [incorrect] Learner Permit (Document) -REQUIRES-> proof of both identity and age (Requirement)
- `annotation_v2_0043` [incorrect] Non - Driver ID card (Document) -REQUIRES-> proof of both identity and age (Requirement)
- `annotation_v2_0044` [incorrect] NY State Driver License (Document) -ALTERNATIVE_TO-> other kinds of proof (Document)

## Register a leased vehicle#1_0::51

> Do it at the DMV: Bring your completed registration application and additional documents to a local DMV office [12]. Make a reservation online before visiting DMV offices in New York City, Westchester, Nassau, Suffolk, Rockland, Onondaga or Monroe Counties. Make a Reservation [13 ]

Gold facts:
- (none)

v2 triples:
- `annotation_v2_0045` [correct] register a leased vehicle (Service) -REQUIRES-> completed registration application (Document)
- `annotation_v2_0046` [correct] register a leased vehicle (Service) -REQUIRES-> additional documents (Document)
- `annotation_v2_0047` [correct] register a leased vehicle (Service) -AVAILABLE_AT-> local DMV office (ContactPoint)
- `annotation_v2_0048` [correct] register a leased vehicle (Service) -REQUIRES-> reservation (Requirement)
- `annotation_v2_0049` [incorrect] reservation online (Service) -PROVIDED_BY-> DMV offices (Organization)

## Appeal A Decision | Social Security Administration#2_0::1

> If you were recently denied Social Security benefits or Supplemental Security Income SSI , you may request an appeal. Generally , you have 60 days after you receive the notice of our decision to ask for any type of appeal. There are four levels of appeal : Reconsideration , Hearing by an administrative law judge , Review by the Appeals Council , and Federal Court review Please see the bottom of page for information on the Federal Court Review Process. You can request an appeal online for a reconsideration, a hearing by an administrative law judge, and a review by the Appeals Council, even if you live outside of the United States. When we made the first determination on your claim , we sent you a letter explaining our determination. This letter contains guidance on what level of appeal you should select. To learn more about each appeal level , visit Information About Social Security's Hearings and Appeals Process.

Gold facts:
- `t0049` appeal (Service) -REQUIRES-> notice (Document)
- `t0050` appeal (Service) -HAS_TIME_LIMIT-> 60 days (TimeLimit)
- `m17` appeal (Service) -APPLIES_TO-> Social Security benefits (Service)
- `m18` appeal (Service) -APPLIES_TO-> Supplemental Security Income (SSI) (Service)
- `m19` Reconsideration (Service) -PART_OF-> appeal (Service)
- `m20` Hearing by an administrative law judge (Service) -PART_OF-> appeal (Service)
- `m21` Review by the Appeals Council (Service) -PART_OF-> appeal (Service)
- `m22` Federal Court review (Service) -PART_OF-> appeal (Service)
- `m23` Reconsideration (Service) -AVAILABLE_AT-> online (ContactPoint)
- `m24` Hearing by an administrative law judge (Service) -AVAILABLE_AT-> online (ContactPoint)
- `m25` Review by the Appeals Council (Service) -AVAILABLE_AT-> online (ContactPoint)

v2 triples:
- `annotation_v2_0050` [incorrect] request an appeal (Service) -REQUIRES-> any type of appeal (Requirement)
- `annotation_v2_0051` [correct, t0049] request an appeal (Service) -REQUIRES-> notice of our decision (Document)
- `annotation_v2_0052` [incorrect] request an appeal (Service) -PART_OF-> Reconsideration (Service)
- `annotation_v2_0053` [incorrect] request an appeal (Service) -PART_OF-> Hearing by an administrative law judge (Service)
- `annotation_v2_0054` [incorrect] request an appeal (Service) -PART_OF-> Review by the Appeals Council (Service)
- `annotation_v2_0055` [incorrect] request an appeal (Service) -PART_OF-> Federal Court review (Service)

## Appeal A Decision | Social Security Administration#2_0::17

> Request a Reconsideration Online for a Medical Determination If your disability claim was recently denied for medical reasons , you can request an appeal online. A reconsideration is a complete review of your claim by someone who did not take part in the first determination. We will look at all the evidence submitted used in the original determination, plus any new evidence. Request Medical ReconsiderationContinue Request for Medical Reconsideration You Started

Gold facts:
- `t0057` Request a Reconsideration Online for a Medical Determination (Service) -REQUIRES-> disability claim (Requirement)
- `t0058` Request a Reconsideration Online for a Medical Determination (Service) -REQUIRES-> medical reasons (Requirement)
- `t0061` Request a Reconsideration Online for a Medical Determination (Service) -LEADS_TO-> reconsideration (Outcome)

v2 triples:
- `annotation_v2_0056` [correct, t0058] request an appeal online (Service) -REQUIRES-> medical reasons (Requirement)
- `annotation_v2_0057` [correct, t0061] request an appeal online (Service) -LEADS_TO-> reconsideration (Service)
- `annotation_v2_0058` [incorrect] reconsideration (Service) -REQUIRES-> evidence submitted used in the original determination (Document)
- `annotation_v2_0059` [incorrect] reconsideration (Service) -REQUIRES-> new evidence (Document)

## Appeal A Decision | Social Security Administration#2_0::23

> Request a Reconsideration Online for a Non-Medical Determination If you received a non - medical determination letter from us that you disagree with or you were denied for a reason that is not disability related for example: income, resources, overpayments, living arrangements, you can request a non - medical appeal online. Request Non - Medical Reconsideration

Gold facts:
- `t0063` Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> non - medical determination letter (Document)
- `t0064` Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> reason that is not disability related (Requirement)
- `t0065` Request a Reconsideration Online for a Non-Medical Determination (Service) -LEADS_TO-> non - medical appeal online (Service)

v2 triples:
- `annotation_v2_0060` [correct, t0063] Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> non - medical determination letter (Document)
- `annotation_v2_0061` [correct, t0064] Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> reason that is not disability related (Requirement)
- `annotation_v2_0062` [incorrect] Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> income (Requirement)
- `annotation_v2_0063` [incorrect] Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> resources (Requirement)
- `annotation_v2_0064` [incorrect] Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> overpayments (Requirement)
- `annotation_v2_0065` [incorrect] Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> living arrangements (Requirement)
- `annotation_v2_0066` [incorrect] non - medical appeal online (Service) -PROVIDED_BY-> Social Security Administration (Organization)

## Appeal A Decision | Social Security Administration#2_0::26

> Check the Status of Your Reconsideration Whether you applied online, by phone, or in an office , you can check the status of your disability and SSI Reconsideration using your personal my Social Security account. A my Social Security account is an easy, convenient, and secure way to do business with us. If you don t have one , you can create one today. Sign In or Create Account

Gold facts:
- `t0068` Check the Status of Your Reconsideration (Service) -APPLIES_TO-> disability and SSI Reconsideration (Service)
- `t0069` Check the Status of Your Reconsideration (Service) -AVAILABLE_AT-> my Social Security account (ContactPoint)

v2 triples:
- `annotation_v2_0067` [incorrect] check the status of your disability and SSI Reconsideration (Service) -REQUIRES-> my Social Security account (Document)
- `annotation_v2_0068` [incorrect] create one today (Requirement) -LEADS_TO-> check the status of your disability and SSI Reconsideration (Service)

## Appeal A Decision | Social Security Administration#2_0::33

> Request a Hearing for a Medical Determination Online A hearing is conducted by an administrative law judge who had no part in the original determination or the reconsideration of your case. The hearing is usually held within 75 miles of your home. If you disagree with the determination we made at the reconsideration level , you may request a hearing online. You Started Request Medical HearingContinue Medical Hearing Request

Gold facts:
- `m26` Request a Hearing for a Medical Determination Online (Service) -REQUIRES-> reconsideration (Service)

v2 triples:
- `annotation_v2_0069` [incorrect] Request a hearing for a medical determination online (Service) -REQUIRES-> reconsideration level determination (Requirement)
- `annotation_v2_0070` [incorrect] hearing (Service) -PROVIDED_BY-> administrative law judge (Organization)
- `annotation_v2_0071` [incorrect] hearing (Service) -HAS_TIME_LIMIT-> within 75 miles of your home (TimeLimit)

## Appeal A Decision | Social Security Administration#2_0::40

> Request a Hearing for a Non-Medical Determination Online If you requested a reconsideration and received a non - medical determination letter from us that you disagree with or you were denied benefits for a reason that is not disability related for example: income, resources, overpayments, living arrangements , you can request a non - medical hearing online. Request Non - Medical Hearing

Gold facts:
- `t0074` Request a Hearing for a Non-Medical Determination Online (Service) -REQUIRES-> reconsideration (Service)
- `t0075` Request a Hearing for a Non-Medical Determination Online (Service) -REQUIRES-> non - medical determination letter (Document)
- `t0078` Request a Hearing for a Non-Medical Determination Online (Service) -LEADS_TO-> non - medical hearing (Service)

v2 triples:
- `annotation_v2_0072` [correct, t0074] Request a Hearing for a Non-Medical Determination online (Service) -REQUIRES-> reconsideration (Service)
- `annotation_v2_0073` [correct, t0075] Request a Hearing for a Non-Medical Determination online (Service) -REQUIRES-> non - medical determination letter (Document)
- `annotation_v2_0074` [correct] Request a Hearing for a Non-Medical Determination online (Service) -REQUIRES-> reason that is not disability related (Requirement)
- `annotation_v2_0075` [correct, t0078] Request a Hearing for a Non-Medical Determination online (Service) -LEADS_TO-> non - medical hearing online (Service)

## Appeal A Decision | Social Security Administration#2_0::44

> Check the Status of Your Hearing Whether you applied online, by phone, or in an office , you can check the status of your disability and SSI hearing using your personal my Social Security account. A my Social Security account is an easy, convenient, and secure way to do business with us. If you don t have one , you can create one today. Sign In or Create Account

Gold facts:
- (none)

v2 triples:
- `annotation_v2_0076` [incorrect] check the status of your disability and SSI hearing (Service) -REQUIRES-> my Social Security account (Document)
- `annotation_v2_0077` [incorrect] check the status of your disability and SSI hearing (Service) -REQUIRES-> create one today (Requirement)

## Appeal A Decision | Social Security Administration#2_0::51

> Request an Appeals Council review of a decision or dismissal made by an administrative law judge The Appeals Council looks at all requests for review , but it may deny a request if it believes the hearing decision was supported and in accordance with social security law and regulations. If the Appeals Council decides to review your case , it will either decide your case itself or return it to an administrative law judge for further review. If you disagree with the hearing decision , you may request a review by Social Security s Appeals Council online. Request Appeals Council Review If you disagree with the Appeals Council's decision, or if the Appeals Council decides not to review your case , you can file a civil suit in a federal district court. This is the last level of the appeals process. Currently , this process is not available online. To learn more about this process , visit Federal Court Review Process. You can also file an appeal by calling our toll - free number , 1 - 800 - 772 - 1213 TTY 1 - 800 - 325 - 0778 or contacting your local Social Security office.

Gold facts:
- `t0082` Appeals Council review (Service) -PROVIDED_BY-> Appeals Council (Organization)
- `t0085` Appeals Council review (Service) -AVAILABLE_AT-> 1 - 800 - 772 - 1213 (ContactPoint)
- `t0086` Appeals Council review (Service) -AVAILABLE_AT-> 1 - 800 - 325 - 0778 (ContactPoint)
- `t0087` Appeals Council review (Service) -AVAILABLE_AT-> Social Security office (Organization)
- `m28` Appeals Council review (Service) -AVAILABLE_AT-> online (ContactPoint)

v2 triples:
- `annotation_v2_0078` [correct, t0082] Appeals Council review of a decision or dismissal (Service) -PROVIDED_BY-> Appeals Council (Organization)
- `annotation_v2_0079` [incorrect] Appeals Council review of a decision or dismissal (Service) -LEADS_TO-> review your case (Outcome)
- `annotation_v2_0080` [incorrect] Appeals Council review of a decision or dismissal (Service) -ALTERNATIVE_TO-> Social Security's Appeals Council online (Service)
- `annotation_v2_0081` [incorrect] civil suit in a federal district court (Service) -EXEMPT_FROM-> this process is not available online (Requirement)
- `annotation_v2_0082` [incorrect] civil suit in a federal district court (Service) -AVAILABLE_AT-> 1-800-772-1213 (ContactPoint)
- `annotation_v2_0083` [incorrect] civil suit in a federal district court (Service) -AVAILABLE_AT-> TTY 1-800-325-0778 (ContactPoint)
- `annotation_v2_0084` [incorrect] civil suit in a federal district court (Service) -AVAILABLE_AT-> local Social Security office (ContactPoint)

## VA Housing Assistance | Veterans Affairs#1_0::1

> VA housing assistance VA housing assistance can help Veterans, service members, and their surviving spouses to buy a home or refinance a loan. We also offer benefits and services to help you build, improve, or keep your current home. Find out how to apply for and manage the Veterans housing assistance benefits you've earned.

Gold facts:
- `t0088` VA housing assistance (Service) -APPLIES_TO-> Veterans (Role)
- `t0089` VA housing assistance (Service) -APPLIES_TO-> service members (Role)
- `t0090` VA housing assistance (Service) -APPLIES_TO-> surviving spouses (Role)
- `t0091` VA housing assistance (Service) -LEADS_TO-> buy a home (Outcome)
- `t0092` VA housing assistance (Service) -LEADS_TO-> refinance a loan (Outcome)
- `t0093` VA housing assistance (Service) -LEADS_TO-> build, improve, or keep your current home (Outcome)

v2 triples:
- `annotation_v2_0085` [correct, t0088] VA housing assistance (Service) -APPLIES_TO-> Veterans (Role)
- `annotation_v2_0086` [correct, t0089] VA housing assistance (Service) -APPLIES_TO-> service members (Role)
- `annotation_v2_0087` [correct, t0090] VA housing assistance (Service) -APPLIES_TO-> surviving spouses (Role)
- `annotation_v2_0088` [incorrect] VA housing assistance (Service) -LEADS_TO-> buy a home (Service)
- `annotation_v2_0089` [incorrect] VA housing assistance (Service) -LEADS_TO-> refinance a loan (Service)
- `annotation_v2_0090` [incorrect] VA housing assistance (Service) -LEADS_TO-> benefits and services to help you build, improve, or keep your current home (Service)

## VA Housing Assistance | Veterans Affairs#1_0::24

> Get VA Home Loan Benefits About VA Home Loan TypesLearn how VA direct and VA - backed home loans work and find out which loan type may be right for you. EligibilityFind out if you're eligible for a VA direct or VA - backed home loan, based on your service history and duty status. How to Apply for Your Certificate of EligibilityGet instructions for how to apply for your VA home loan Certificate of Eligibility COE and what to do next depending on your loan type. VA Home Loan Programs for Surviving SpousesFind out if you're eligible and how to apply for a VA home loan COE as the surviving spouse of a Veteran or the spouse of a Veteran who is missing in action or being held as a Prisoner of War. Check Your Appeal StatusTrack the status of an open home loan COE appeal. Having Trouble Making Payments on a VA - Backed Mortgage? Get help to avoid foreclosure if you're struggling to make your monthly mortgage payments. A Warning about Home Loan Refinancing OffersLearn about the signs of misleading offers to refinance your VA - backed home loan, like claims that you can skip payments or get very low interest rates or other terms that sound too good to be true. Home Buying Process for VeteransWatch a video and get more information about using your VA home loan benefit to buy a home. VA Loan Funding FeeFind out if you'll need to pay this fee when using your home loan benefits. Find a VA Regional Loan CenterLook up contact information for your nearest regional loan center. Find VA - Acquired PropertiesLearn more about buying a home we've acquired because its VA - direct or VA - backed home loan was terminated. how to get help if you have a VA direct or VA - backed home loan or Specially Adapted Housing grant Guidance on Natural DisastersFind out and your home was damaged by a natural disaster.

Gold facts:
- `t0096` VA direct home loan (Service) -REQUIRES-> service history (Requirement)
- `t0097` VA direct home loan (Service) -REQUIRES-> duty status (Requirement)
- `t0098` VA - backed home loan (Service) -REQUIRES-> service history (Requirement)
- `t0099` VA - backed home loan (Service) -REQUIRES-> duty status (Requirement)
- `t0102` VA home loan (Service) -APPLIES_TO-> surviving spouse of a Veteran (Role)
- `t0103` VA home loan (Service) -APPLIES_TO-> spouse of a Veteran who is missing in action or being held as a Prisoner of War (Role)
- `t0110` VA Loan Funding Fee (Service) -REQUIRES-> VA home loan benefit (Service)
- `m27` Check Your Appeal Status (Service) -APPLIES_TO-> home loan COE appeal (Service)
- `m29` VA direct home loan (Service) -PART_OF-> VA home loan (Service)
- `m30` VA - backed home loan (Service) -PART_OF-> VA home loan (Service)
- `m31` Find a VA Regional Loan Center (Service) -AVAILABLE_AT-> contact information for your nearest regional loan center (ContactPoint)

v2 triples:
- `annotation_v2_0091` [incorrect] VA direct or VA-backed home loan (Service) -REQUIRES-> Eligibility (Requirement)
- `annotation_v2_0092` [incorrect] apply for your VA home loan Certificate of Eligibility (COE) (Service) -REQUIRES-> Certificate of Eligibility (COE) (Document)
- `annotation_v2_0093` [correct, t0102] apply for your VA home loan Certificate of Eligibility (COE) (Service) -APPLIES_TO-> surviving spouse of a Veteran (Role)
- `annotation_v2_0094` [correct, t0103] apply for your VA home loan Certificate of Eligibility (COE) (Service) -APPLIES_TO-> spouse of a Veteran who is missing in action or being held as a Prisoner of War (Role)
- `annotation_v2_0095` [incorrect] open home loan COE appeal (Service) -LEADS_TO-> appeal status (Outcome)
- `annotation_v2_0096` [correct] Having Trouble Making Payments on a VA - Backed Mortgage? Get help to avoid foreclosure (Service) -LEADS_TO-> avoid foreclosure (Outcome)
- `annotation_v2_0097` [correct] Home Buying Process for Veterans (Service) -APPLIES_TO-> VA home loan benefit (Service)
- `annotation_v2_0098` [incorrect] VA Loan Funding Fee (Service) -REQUIRES-> pay this fee (Requirement)
- `annotation_v2_0099` [incorrect] VA - Acquired Properties (Service) -REQUIRES-> home was damaged by a natural disaster (Requirement)

## VA Housing Assistance | Veterans Affairs#1_0::39

> Get Veterans Housing Assistance Grants About Disability Housing Grants for VeteransFind out how to apply for a housing grant as a Veteran or Servicemember with a service - connected disability. Apply for a Specially Adapted Housing GrantGet financial help to make changes to your home to help you live more independently with a service - connected disability. Check Your SAH Grant Claim StatusTrack the status of an open claim for a Specially Adapted Housing grant.

Gold facts:
- `t0113` housing grant (Service) -REQUIRES-> service - connected disability (Requirement)
- `t0114` housing grant (Service) -APPLIES_TO-> Veteran or Servicemember (Role)
- `t0115` Specially Adapted Housing Grant (Service) -REQUIRES-> service - connected disability (Requirement)
- `t0116` SAH Grant Claim Status (Service) -REQUIRES-> open claim (Requirement)
- `t0117` SAH Grant Claim Status (Service) -APPLIES_TO-> Specially Adapted Housing grant (Service)
- `m32` housing grant (Service) -PART_OF-> Veterans Housing Assistance Grants (Service)

v2 triples:
- `annotation_v2_0100` [incorrect] Veterans Housing Assistance Grants (Service) -PART_OF-> Disability Housing Grants for Veterans (Service)
- `annotation_v2_0101` [correct, t0114] housing grant (Service) -APPLIES_TO-> Veteran (Role)
- `annotation_v2_0102` [correct, t0114] housing grant (Service) -APPLIES_TO-> Servicemember (Role)
- `annotation_v2_0103` [correct, t0113] housing grant (Service) -REQUIRES-> service - connected disability (Requirement)
- `annotation_v2_0104` [correct, t0115] Specially Adapted Housing Grant (Service) -REQUIRES-> service - connected disability (Requirement)
- `annotation_v2_0105` [correct, t0116] SAH Grant Claim Status (Service) -REQUIRES-> open claim for a Specially Adapted Housing grant (Requirement)

## VA Housing Assistance | Veterans Affairs#1_0::43

> Other VA Benefits and Services Disability Compensation Pay Find out how to file a claim for compensation for conditions related to your military service. Pension BenefitsSee if you qualify for pension benefits as a wartime Veteran or a surviving spouse or child. Vocational Rehabilitation and Employment VR&E If your service - connected disability limits your ability to work or prevents you from working , find out if you can get VR&E benefits and services like help exploring employment options and getting more training if required. Life insuranceExplore your life insurance options and find out how to apply as a service member, Veteran, or family member.

Gold facts:
- `t0118` Pension Benefits (Service) -APPLIES_TO-> wartime Veteran (Role)
- `t0119` Pension Benefits (Service) -APPLIES_TO-> surviving spouse or child (Role)
- `t0120` Vocational Rehabilitation and Employment (VR&E) (Service) -REQUIRES-> service - connected disability (Requirement)
- `t0121` Life insurance (Service) -APPLIES_TO-> service member (Role)
- `t0122` Life insurance (Service) -APPLIES_TO-> Veteran (Role)
- `t0123` Life insurance (Service) -APPLIES_TO-> family member (Role)
- `m33` Vocational Rehabilitation and Employment (VR&E) (Service) -LEADS_TO-> help exploring employment options (Outcome)
- `m34` Vocational Rehabilitation and Employment (VR&E) (Service) -LEADS_TO-> getting more training (Outcome)

v2 triples:
- `annotation_v2_0106` [correct, t0118] Pension Benefits (Service) -APPLIES_TO-> wartime Veteran (Role)
- `annotation_v2_0107` [correct, t0119] Pension Benefits (Service) -APPLIES_TO-> surviving spouse (Role)
- `annotation_v2_0108` [correct, t0119] Pension Benefits (Service) -APPLIES_TO-> child (Role)
- `annotation_v2_0109` [correct, t0120] Vocational Rehabilitation and Employment (VR&E) (Service) -REQUIRES-> service - connected disability (Requirement)

## VA Housing Assistance | Veterans Affairs#1_0::49

> National Call Center for Homeless Veterans Find out how we can help you or a Veteran you care about connect with VA and local resources 24 hours a day , 7 days a week.

Gold facts:
- `t0125` National Call Center for Homeless Veterans (Service) -HAS_TIME_LIMIT-> 24 hours a day (TimeLimit)
- `t0126` National Call Center for Homeless Veterans (Service) -HAS_TIME_LIMIT-> 7 days a week (TimeLimit)
- `t0127` National Call Center for Homeless Veterans (Service) -APPLIES_TO-> Veteran you care about (Role)

v2 triples:
- `annotation_v2_0110` [incorrect] National Call Center for Homeless Veterans (Service) -PROVIDED_BY-> VA (Organization)
- `annotation_v2_0111` [correct, t0125] National Call Center for Homeless Veterans (Service) -HAS_TIME_LIMIT-> 24 hours a day , 7 days a week (TimeLimit)

## VA Housing Assistance | Veterans Affairs#1_0::8

> How do I get help if I'm homeless or at risk of becoming homeless? We offer many programs and services that may help including free health care and, in some cases, free limited dental care. We can also help you connect with resources in your community, like homeless shelters or faith - based organizations. Find the support you need : Call the National Call Center for Homeless Veterans at 877 - 424 - 3838 for help 24 hours a day , 7 days a week. You ll talk privately with a trained VA counselor for free. Contact your nearest VA medical center and ask to talk with the VA social worker. If you're a female Veteran , ask for the Women Veterans Program Manager. Find the nearest VA medical center Talk with someone right now : If you're a Veteran in crisis or concerned about one , connect with our caring, qualified Veterans Crisis Line responders for confidential help. Many of them are Veterans themselves. This service is private, free, and available 24/7. Chat online with a trained VA staff member

Gold facts:
- `t0135` free health care (Service) -PROVIDED_BY-> VA medical center (Organization)
- `t0136` free limited dental care (Service) -PROVIDED_BY-> VA medical center (Organization)
- `t0137` National Call Center for Homeless Veterans (Organization) -AVAILABLE_AT-> 877 - 424 - 3838 (ContactPoint)
- `t0138` Veterans Crisis Line (Service) -LEADS_TO-> confidential help (Outcome)
- `t0139` Veterans Crisis Line (Service) -HAS_TIME_LIMIT-> 24/7 (TimeLimit)
- `m38` Chat online with a trained VA staff member (Service) -AVAILABLE_AT-> online (ContactPoint)

v2 triples:
- `annotation_v2_0112` [incorrect] programs and services (Service) -PROVIDED_BY-> nearest VA medical center (Organization)
- `annotation_v2_0113` [incorrect] programs and services (Service) -AVAILABLE_AT-> National Call Center for Homeless Veterans (Organization)
- `annotation_v2_0114` [incorrect] programs and services (Service) -HAS_TIME_LIMIT-> help 24 hours a day , 7 days a week (TimeLimit)
- `annotation_v2_0115` [incorrect] programs and services (Service) -AVAILABLE_AT-> 877 - 424 - 3838 (ContactPoint)
- `annotation_v2_0116` [correct] free health care (Service) -PART_OF-> programs and services (Service)
- `annotation_v2_0117` [correct] free limited dental care (Service) -PART_OF-> programs and services (Service)
- `annotation_v2_0118` [incorrect] programs and services (Service) -APPLIES_TO-> trained VA counselor (Role)
- `annotation_v2_0119` [incorrect] programs and services (Service) -APPLIES_TO-> Women Veterans Program Manager (Role)
- `annotation_v2_0120` [incorrect] programs and services (Service) -APPLIES_TO-> VA social worker (Role)
- `annotation_v2_0121` [correct, t0138] Veterans Crisis Line (Service) -LEADS_TO-> confidential help (Outcome)
- `annotation_v2_0122` [correct, t0139] Veterans Crisis Line (Service) -HAS_TIME_LIMIT-> help 24 hours a day , 7 days a week (TimeLimit)
- `annotation_v2_0123` [incorrect] Chat online with a trained VA staff member (Service) -APPLIES_TO-> trained VA counselor (Role)
