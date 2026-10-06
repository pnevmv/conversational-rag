# Sections with their v1 triples

For each section: the text, then the triples prompt v1 extracted from it (with your label). Facts that are stated in the text but have no correct triple below go into `2_missing_v1.csv`.


## Register a leased vehicle#1

### Register a leased vehicle#1_0::1 (not extracted: short or boilerplate)

> Register a leased vehicle[1]

- (no triples)

### Register a leased vehicle#1_0::11

> Summary of what you need a certified copy of the title certificate , original Manufacturers Statement of Origin MSO or Manufacturer's Certificate of Origin MCO 1 current NY State Insurance ID card auto liability insurance 2 NY State driver license , permit , non - driver ID , or other proof of identity 3 authorization from the leasing company to register the vehicle in New York, which consists of all these things a letter from the leasing company that gives you permission to register the vehicle in NY State a power of attorney from the leasing company that authorizes you to register the vehicle in NY State the signature of a leasing company officer in box 3 on the Vehicle Registration / Title Application PDF [3] MV-82 or on the Registration Authorization PDF [4] MV-95 proof of sales tax payment, sales tax exemption, or purchase price see below for instructions for to show proof

- [correct] t0001: authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> letter from the leasing company that gives you permission to register the vehicle in NY State (Document)
- [correct] t0002: authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> power of attorney from the leasing company that authorizes you to register the vehicle in NY State (Document)
- [correct] t0003: authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> Vehicle Registration / Title Application PDF (MV-82) (Document)
- [correct] t0004: authorization from the leasing company to register the vehicle in New York (Requirement) -REQUIRES-> Registration Authorization PDF (MV-95) (Document)

### Register a leased vehicle#1_0::2

> How to register a leased vehicle If you leased the vehicle from a dealer in New York State , the dealer normally registers the vehicle for you by providing all your proofs and your registration application to the DMV. In this case , you don t need to do anything more. If the dealer does not provide the proofs to the DMV , you must register the vehicle at a DMV office. Please complete the Document Guide to make sure you bring the correct documents with you. Find your proofs [2 ]

- [incorrect] t0005: register a leased vehicle (Service) -PROVIDED_BY-> DMV (Organization)
- [correct] t0006: register a leased vehicle (Service) -REQUIRES-> proofs (Document)
- [correct] t0007: register a leased vehicle (Service) -REQUIRES-> registration application (Document)
- [incorrect] t0008: register a leased vehicle (Service) -REQUIRES-> If the dealer does not provide the proofs to the DMV (Requirement)
- [incorrect] t0009: register a leased vehicle (Service) -REQUIRES-> bring the correct documents with you (Requirement)
- [incorrect] t0010: register a leased vehicle (Service) -REQUIRES-> Find your proofs (Requirement)
- [correct] t0011: register a leased vehicle (Service) -AVAILABLE_AT-> DMV office (ContactPoint)
- [correct] t0012: register a leased vehicle (Service) -REQUIRES-> Document Guide (Document)

### Register a leased vehicle#1_0::25

> Proof of sales tax payment If you paid New York State sales tax to the leasing company or dealer on the total amount of all your lease payments , provide your lease agreement that indicates that you paid the NY State sales tax, and complete the Claim for Sales Tax Exemption {Sales Tax Form} PDF [5] at NY State Department of Tax and Finance DTF-803. If you did not pay New York State sales tax to the leasing company or dealer on all of your lease payments , provide your lease agreement , and complete Statement of Transaction {Sales Tax Form} PDF [6] at NY State Department of Tax and Finance DTF-802. You must pay NY State sales tax at the DMV office on any lease payments if the leasing company or dealer did not collect the sales tax. The sales tax is collected in one complete payment at the time of registration. If you made one payment to another state for the total amount of sales tax, complete Claim for Credit of Sales Tax Paid to Another State {Sales Tax Form} PDF [7] at NY State Department of Tax and Finance DTF-804 to request credit for the tax you paid, and then pay the balance of any NY State sales tax. This process can reduce the amount of your NY State sales tax if NY State and the other state have an agreement about sales tax. Not all states have an agreement with New York. See DFT-804 page 2. If you made monthly sales tax payments in another state, complete form Statement of Transaction {Sales Tax Form} PDF [6] at NY State Department of Tax and Finance DTF-802, and pay the total amount of NY State sales tax in one payment for all the lease payments that remain. See also Change name on title after lease buyout [8]. You will not receive the original title certificate as proof of ownership. The leasing company is the owner and holds the title certificate, which displays their name. Your insurance company will: 1) give you 2 barcoded original NY State Insurance ID cards (see a sample [9]) or provide you with access to your digital electronic NY State Insurance ID Card 2) send an electronic notice of insurance coverage to the DMV (your insurance agent or broker cannot file this notice) Your NY State Insurance ID cards and the electronic notice together verify your coverage. We need both. You must register your vehicle within 180 days of the effective date on your Insurance ID Card. Bring one copy or form of your Insurance ID Card with you. The DMV office will keep the paper card. Keep the other paper card with the vehicle as your proof of insurance. Anyone operating your vehicle must be able to provide proof of insurance. Learn more about NY State Insurance Requirements [10]. You must be at least 16 years old except for ATV registrations. You can use a NY State Driver License, Learner Permit, or Non - Driver ID card that is current or not expired for more than 2 years as proof of both identity and age . If you don t have one of these, see other kinds of proof [11] you can use.

- [correct] t0013: Proof of sales tax payment (Requirement) -REQUIRES-> lease agreement (Document)
- [correct] t0014: Proof of sales tax payment (Requirement) -REQUIRES-> Claim for Sales Tax Exemption (Document)
- [correct] t0015: Proof of sales tax payment (Requirement) -REQUIRES-> Statement of Transaction (Document)
- [correct] t0016: Proof of sales tax payment (Requirement) -REQUIRES-> Claim for Credit of Sales Tax Paid to Another State (Document)
- [correct] t0017: Claim for Sales Tax Exemption (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- [correct] t0018: Statement of Transaction (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- [correct] t0019: Claim for Credit of Sales Tax Paid to Another State (Document) -PROVIDED_BY-> NY State Department of Tax and Finance (Organization)
- [incorrect] t0020: NY State sales tax (Requirement) -LEADS_TO-> sales tax is collected in one complete payment at the time of registration (Outcome)
- [correct] t0021: register your vehicle (Service) -HAS_TIME_LIMIT-> 180 days (TimeLimit)
- [incorrect] t0022: register your vehicle (Service) -REQUIRES-> both (Requirement)
- [correct] t0023: register your vehicle (Service) -REQUIRES-> proof of insurance (Requirement)
- [correct] t0024: register your vehicle (Service) -REQUIRES-> at least 16 years old (Requirement)
- [incorrect] t0025: NY State Insurance ID cards (Document) -PROVIDED_BY-> DMV (Organization)
- [incorrect] t0026: electronic notice of insurance coverage (Document) -AVAILABLE_AT-> DMV (Organization)
- [incorrect] t0027: register your vehicle (Service) -LEADS_TO-> proof of ownership (Outcome)
- [correct] t0028: NY State Driver License (Service) -REQUIRES-> proof of both identity and age (Requirement)
- [correct] t0029: Learner Permit (Service) -REQUIRES-> proof of both identity and age (Requirement)
- [correct] t0030: Non - Driver ID card (Service) -REQUIRES-> proof of both identity and age (Requirement)
- [incorrect] t0031: NY State Driver License (Service) -HAS_TIME_LIMIT-> 2 years (TimeLimit)
- [incorrect] t0032: Learner Permit (Service) -HAS_TIME_LIMIT-> 2 years (TimeLimit)
- [incorrect] t0033: Non - Driver ID card (Service) -HAS_TIME_LIMIT-> 2 years (TimeLimit)
- [incorrect] t0034: NY State Driver License (Service) -REQUIRES-> current or not expired for more than 2 years (Requirement)
- [incorrect] t0035: Learner Permit (Service) -REQUIRES-> current or not expired for more than 2 years (Requirement)
- [incorrect] t0036: Non - Driver ID card (Service) -REQUIRES-> current or not expired for more than 2 years (Requirement)
- [incorrect] t0037: NY State Driver License (Service) -ALTERNATIVE_TO-> other kinds of proof (Service)

### Register a leased vehicle#1_0::51

> Do it at the DMV: Bring your completed registration application and additional documents to a local DMV office [12]. Make a reservation online before visiting DMV offices in New York City, Westchester, Nassau, Suffolk, Rockland, Onondaga or Monroe Counties. Make a Reservation [13 ]

- [incorrect] t0038: registration application (Document) -REQUIRES-> completed registration application (Requirement)
- [incorrect] t0039: additional documents (Document) -REQUIRES-> completed registration application (Requirement)
- [incorrect] t0040: reservation online (Service) -REQUIRES-> reservation online before visiting DMV offices (Requirement)
- [incorrect] t0041: reservation online (Service) -APPLIES_TO-> New York City (Role)
- [incorrect] t0042: reservation online (Service) -APPLIES_TO-> Westchester County (Role)
- [incorrect] t0043: reservation online (Service) -APPLIES_TO-> Nassau County (Role)
- [incorrect] t0044: reservation online (Service) -APPLIES_TO-> Suffolk County (Role)
- [incorrect] t0045: reservation online (Service) -APPLIES_TO-> Rockland County (Role)
- [incorrect] t0046: reservation online (Service) -APPLIES_TO-> Onondaga County (Role)
- [incorrect] t0047: reservation online (Service) -APPLIES_TO-> Monroe County (Role)
- [incorrect] t0048: DMV (Organization) -AVAILABLE_AT-> local DMV office (ContactPoint)

### Register a leased vehicle#1_0::55 (not extracted: short or boilerplate)

> Show "do it online" button in megamenu:

- (no triples)

### Register a leased vehicle#1_0::56 (not extracted: short or boilerplate)

> Topic: Registration [14 ]

- (no triples)

### Register a leased vehicle#1_0::58 (not extracted: short or boilerplate)

> Related PDFs:

- (no triples)

### Register a leased vehicle#1_0::59 (not extracted: short or boilerplate)

> show mydmv button in megamenu:

- (no triples)

### Register a leased vehicle#1_0::60 (not extracted: short or boilerplate)

> Disable this transaction?:

- (no triples)

### Register a leased vehicle#1_0::61 (not extracted: short or boilerplate)

> yes or no survey:

- (no triples)


## Appeal A Decision | Social Security Administration#2

### Appeal A Decision | Social Security Administration#2_0::1

> If you were recently denied Social Security benefits or Supplemental Security Income SSI , you may request an appeal. Generally , you have 60 days after you receive the notice of our decision to ask for any type of appeal. There are four levels of appeal : Reconsideration , Hearing by an administrative law judge , Review by the Appeals Council , and Federal Court review Please see the bottom of page for information on the Federal Court Review Process. You can request an appeal online for a reconsideration, a hearing by an administrative law judge, and a review by the Appeals Council, even if you live outside of the United States. When we made the first determination on your claim , we sent you a letter explaining our determination. This letter contains guidance on what level of appeal you should select. To learn more about each appeal level , visit Information About Social Security's Hearings and Appeals Process.

- [correct] t0049: appeal (Service) -REQUIRES-> notice (Document)
- [correct] t0050: appeal (Service) -HAS_TIME_LIMIT-> 60 days (TimeLimit)
- [incorrect] t0051: letter (Document) -REQUIRES-> guidance on what level of appeal you should select (Requirement)
- [incorrect] t0052: Reconsideration (Service) -APPLIES_TO-> outside of the United States (Role)
- [incorrect] t0053: Hearing by an administrative law judge (Service) -APPLIES_TO-> outside of the United States (Role)
- [incorrect] t0054: Review by the Appeals Council (Service) -APPLIES_TO-> outside of the United States (Role)
- [incorrect] t0055: appeal (Service) -PART_OF-> Social Security benefits (Service)
- [incorrect] t0056: appeal (Service) -PART_OF-> Supplemental Security Income (SSI) (Service)

### Appeal A Decision | Social Security Administration#2_0::17

> Request a Reconsideration Online for a Medical Determination If your disability claim was recently denied for medical reasons , you can request an appeal online. A reconsideration is a complete review of your claim by someone who did not take part in the first determination. We will look at all the evidence submitted used in the original determination, plus any new evidence. Request Medical ReconsiderationContinue Request for Medical Reconsideration You Started

- [correct] t0057: Request a Reconsideration Online for a Medical Determination (Service) -REQUIRES-> disability claim (Requirement)
- [correct] t0058: Request a Reconsideration Online for a Medical Determination (Service) -REQUIRES-> medical reasons (Requirement)
- [incorrect] t0059: Request a Reconsideration Online for a Medical Determination (Service) -REQUIRES-> evidence submitted used in the original determination (Requirement)
- [incorrect] t0060: Request a Reconsideration Online for a Medical Determination (Service) -REQUIRES-> new evidence (Requirement)
- [correct] t0061: Request a Reconsideration Online for a Medical Determination (Service) -LEADS_TO-> reconsideration (Outcome)
- [incorrect] t0062: Request a Reconsideration Online for a Medical Determination (Service) -AVAILABLE_AT-> Request Medical Reconsideration (ContactPoint)

### Appeal A Decision | Social Security Administration#2_0::23

> Request a Reconsideration Online for a Non-Medical Determination If you received a non - medical determination letter from us that you disagree with or you were denied for a reason that is not disability related for example: income, resources, overpayments, living arrangements, you can request a non - medical appeal online. Request Non - Medical Reconsideration

- [correct] t0063: Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> non - medical determination letter (Document)
- [correct] t0064: Request a Reconsideration Online for a Non-Medical Determination (Service) -REQUIRES-> reason that is not disability related (Requirement)
- [correct] t0065: Request a Reconsideration Online for a Non-Medical Determination (Service) -LEADS_TO-> non - medical appeal online (Service)
- [incorrect] t0066: Request a Reconsideration Online for a Non-Medical Determination (Service) -ALTERNATIVE_TO-> Request Non - Medical Reconsideration (Service)
- [incorrect] t0067: non - medical appeal online (Service) -PART_OF-> Request a Reconsideration Online for a Non-Medical Determination (Service)

### Appeal A Decision | Social Security Administration#2_0::26

> Check the Status of Your Reconsideration Whether you applied online, by phone, or in an office , you can check the status of your disability and SSI Reconsideration using your personal my Social Security account. A my Social Security account is an easy, convenient, and secure way to do business with us. If you don t have one , you can create one today. Sign In or Create Account

- [correct] t0068: Check the Status of Your Reconsideration (Service) -APPLIES_TO-> disability and SSI Reconsideration (Service)
- [correct] t0069: Check the Status of Your Reconsideration (Service) -AVAILABLE_AT-> my Social Security account (ContactPoint)

### Appeal A Decision | Social Security Administration#2_0::33

> Request a Hearing for a Medical Determination Online A hearing is conducted by an administrative law judge who had no part in the original determination or the reconsideration of your case. The hearing is usually held within 75 miles of your home. If you disagree with the determination we made at the reconsideration level , you may request a hearing online. You Started Request Medical HearingContinue Medical Hearing Request

- [incorrect] t0070: Request a Hearing for a Medical Determination Online (Service) -REQUIRES-> Request a hearing online (Requirement)
- [incorrect] t0071: hearing (Service) -HAS_TIME_LIMIT-> 75 miles (TimeLimit)
- [incorrect] t0072: hearing (Service) -APPLIES_TO-> administrative law judge (Role)
- [incorrect] t0073: Request a Hearing for a Medical Determination Online (Service) -APPLIES_TO-> reconsideration level (Role)

### Appeal A Decision | Social Security Administration#2_0::40

> Request a Hearing for a Non-Medical Determination Online If you requested a reconsideration and received a non - medical determination letter from us that you disagree with or you were denied benefits for a reason that is not disability related for example: income, resources, overpayments, living arrangements , you can request a non - medical hearing online. Request Non - Medical Hearing

- [correct] t0074: Request a Hearing for a Non-Medical Determination Online (Service) -REQUIRES-> reconsideration (Service)
- [correct] t0075: Request a Hearing for a Non-Medical Determination Online (Service) -REQUIRES-> non - medical determination letter (Document)
- [incorrect] t0076: Request a Hearing for a Non-Medical Determination Online (Service) -REQUIRES-> you disagree with (Requirement)
- [incorrect] t0077: Request a Hearing for a Non-Medical Determination Online (Service) -REQUIRES-> income, resources, overpayments, living arrangements (Requirement)
- [correct] t0078: Request a Hearing for a Non-Medical Determination Online (Service) -LEADS_TO-> non - medical hearing (Service)
- [incorrect] t0079: Request a Hearing for a Non-Medical Determination Online (Service) -AVAILABLE_AT-> Request Non - Medical Hearing (ContactPoint)

### Appeal A Decision | Social Security Administration#2_0::44

> Check the Status of Your Hearing Whether you applied online, by phone, or in an office , you can check the status of your disability and SSI hearing using your personal my Social Security account. A my Social Security account is an easy, convenient, and secure way to do business with us. If you don t have one , you can create one today. Sign In or Create Account

- [incorrect] t0080: Check the Status of Your Hearing (Service) -REQUIRES-> create one today (Requirement)
- [incorrect] t0081: Sign In or Create Account (Document) -AVAILABLE_AT-> my Social Security account (ContactPoint)

### Appeal A Decision | Social Security Administration#2_0::51

> Request an Appeals Council review of a decision or dismissal made by an administrative law judge The Appeals Council looks at all requests for review , but it may deny a request if it believes the hearing decision was supported and in accordance with social security law and regulations. If the Appeals Council decides to review your case , it will either decide your case itself or return it to an administrative law judge for further review. If you disagree with the hearing decision , you may request a review by Social Security s Appeals Council online. Request Appeals Council Review If you disagree with the Appeals Council's decision, or if the Appeals Council decides not to review your case , you can file a civil suit in a federal district court. This is the last level of the appeals process. Currently , this process is not available online. To learn more about this process , visit Federal Court Review Process. You can also file an appeal by calling our toll - free number , 1 - 800 - 772 - 1213 TTY 1 - 800 - 325 - 0778 or contacting your local Social Security office.

- [correct] t0082: Appeals Council review (Service) -PROVIDED_BY-> Appeals Council (Organization)
- [incorrect] t0083: civil suit in a federal district court (Service) -LEADS_TO-> last level of the appeals process (Outcome)
- [incorrect] t0084: civil suit in a federal district court (Service) -REQUIRES-> not available online (Requirement)
- [correct] t0085: Appeals Council review (Service) -AVAILABLE_AT-> 1 - 800 - 772 - 1213 (ContactPoint)
- [correct] t0086: Appeals Council review (Service) -AVAILABLE_AT-> 1 - 800 - 325 - 0778 (ContactPoint)
- [correct] t0087: Appeals Council review (Service) -AVAILABLE_AT-> Social Security office (Organization)


## VA Housing Assistance | Veterans Affairs#1

### VA Housing Assistance | Veterans Affairs#1_0::1

> VA housing assistance VA housing assistance can help Veterans, service members, and their surviving spouses to buy a home or refinance a loan. We also offer benefits and services to help you build, improve, or keep your current home. Find out how to apply for and manage the Veterans housing assistance benefits you've earned.

- [correct] t0088: VA housing assistance (Service) -APPLIES_TO-> Veterans (Role)
- [correct] t0089: VA housing assistance (Service) -APPLIES_TO-> service members (Role)
- [correct] t0090: VA housing assistance (Service) -APPLIES_TO-> surviving spouses (Role)
- [correct] t0091: VA housing assistance (Service) -LEADS_TO-> buy a home (Outcome)
- [correct] t0092: VA housing assistance (Service) -LEADS_TO-> refinance a loan (Outcome)
- [correct] t0093: VA housing assistance (Service) -LEADS_TO-> build, improve, or keep your current home (Outcome)

### VA Housing Assistance | Veterans Affairs#1_0::24

> Get VA Home Loan Benefits About VA Home Loan TypesLearn how VA direct and VA - backed home loans work and find out which loan type may be right for you. EligibilityFind out if you're eligible for a VA direct or VA - backed home loan, based on your service history and duty status. How to Apply for Your Certificate of EligibilityGet instructions for how to apply for your VA home loan Certificate of Eligibility COE and what to do next depending on your loan type. VA Home Loan Programs for Surviving SpousesFind out if you're eligible and how to apply for a VA home loan COE as the surviving spouse of a Veteran or the spouse of a Veteran who is missing in action or being held as a Prisoner of War. Check Your Appeal StatusTrack the status of an open home loan COE appeal. Having Trouble Making Payments on a VA - Backed Mortgage? Get help to avoid foreclosure if you're struggling to make your monthly mortgage payments. A Warning about Home Loan Refinancing OffersLearn about the signs of misleading offers to refinance your VA - backed home loan, like claims that you can skip payments or get very low interest rates or other terms that sound too good to be true. Home Buying Process for VeteransWatch a video and get more information about using your VA home loan benefit to buy a home. VA Loan Funding FeeFind out if you'll need to pay this fee when using your home loan benefits. Find a VA Regional Loan CenterLook up contact information for your nearest regional loan center. Find VA - Acquired PropertiesLearn more about buying a home we've acquired because its VA - direct or VA - backed home loan was terminated. how to get help if you have a VA direct or VA - backed home loan or Specially Adapted Housing grant Guidance on Natural DisastersFind out and your home was damaged by a natural disaster.

- [incorrect] t0094: VA home loan (Service) -PART_OF-> VA direct home loan (Service)
- [incorrect] t0095: VA home loan (Service) -PART_OF-> VA - backed home loan (Service)
- [correct] t0096: VA direct home loan (Service) -REQUIRES-> service history (Requirement)
- [correct] t0097: VA direct home loan (Service) -REQUIRES-> duty status (Requirement)
- [correct] t0098: VA - backed home loan (Service) -REQUIRES-> service history (Requirement)
- [correct] t0099: VA - backed home loan (Service) -REQUIRES-> duty status (Requirement)
- [incorrect] t0100: VA direct home loan (Service) -REQUIRES-> Certificate of Eligibility (COE) (Document)
- [incorrect] t0101: VA - backed home loan (Service) -REQUIRES-> Certificate of Eligibility (COE) (Document)
- [correct] t0102: VA home loan (Service) -APPLIES_TO-> surviving spouse of a Veteran (Role)
- [correct] t0103: VA home loan (Service) -APPLIES_TO-> spouse of a Veteran who is missing in action or being held as a Prisoner of War (Role)
- [incorrect] t0104: home loan COE appeal (Service) -REQUIRES-> Certificate of Eligibility (COE) (Document)
- [incorrect] t0105: VA - backed mortgage (Service) -REQUIRES-> monthly mortgage payments (Requirement)
- [incorrect] t0106: VA - backed mortgage (Service) -LEADS_TO-> foreclosure (Outcome)
- [incorrect] t0107: VA Regional Loan Center (Organization) -AVAILABLE_AT-> contact information for your nearest regional loan center (ContactPoint)
- [incorrect] t0108: VA home loan benefit (Service) -LEADS_TO-> VA - direct or VA - backed home loan was terminated (Outcome)
- [incorrect] t0109: Guidance on Natural Disasters (Service) -LEADS_TO-> home was damaged by a natural disaster (Outcome)
- [correct] t0110: VA Loan Funding Fee (Service) -REQUIRES-> VA home loan benefit (Service)
- [incorrect] t0111: VA home loan benefit (Service) -REQUIRES-> home loan refinancing offers (Requirement)

### VA Housing Assistance | Veterans Affairs#1_0::39

> Get Veterans Housing Assistance Grants About Disability Housing Grants for VeteransFind out how to apply for a housing grant as a Veteran or Servicemember with a service - connected disability. Apply for a Specially Adapted Housing GrantGet financial help to make changes to your home to help you live more independently with a service - connected disability. Check Your SAH Grant Claim StatusTrack the status of an open claim for a Specially Adapted Housing grant.

- [incorrect] t0112: Veterans Housing Assistance Grants (Service) -PART_OF-> housing grant (Service)
- [correct] t0113: housing grant (Service) -REQUIRES-> service - connected disability (Requirement)
- [correct] t0114: housing grant (Service) -APPLIES_TO-> Veteran or Servicemember (Role)
- [correct] t0115: Specially Adapted Housing Grant (Service) -REQUIRES-> service - connected disability (Requirement)
- [correct] t0116: SAH Grant Claim Status (Service) -REQUIRES-> open claim (Requirement)
- [correct] t0117: SAH Grant Claim Status (Service) -APPLIES_TO-> Specially Adapted Housing grant (Service)

### VA Housing Assistance | Veterans Affairs#1_0::43

> Other VA Benefits and Services Disability Compensation Pay Find out how to file a claim for compensation for conditions related to your military service. Pension BenefitsSee if you qualify for pension benefits as a wartime Veteran or a surviving spouse or child. Vocational Rehabilitation and Employment VR&E If your service - connected disability limits your ability to work or prevents you from working , find out if you can get VR&E benefits and services like help exploring employment options and getting more training if required. Life insuranceExplore your life insurance options and find out how to apply as a service member, Veteran, or family member.

- [correct] t0118: Pension Benefits (Service) -APPLIES_TO-> wartime Veteran (Role)
- [correct] t0119: Pension Benefits (Service) -APPLIES_TO-> surviving spouse or child (Role)
- [correct] t0120: Vocational Rehabilitation and Employment (VR&E) (Service) -REQUIRES-> service - connected disability (Requirement)
- [correct] t0121: Life insurance (Service) -APPLIES_TO-> service member (Role)
- [correct] t0122: Life insurance (Service) -APPLIES_TO-> Veteran (Role)
- [correct] t0123: Life insurance (Service) -APPLIES_TO-> family member (Role)

### VA Housing Assistance | Veterans Affairs#1_0::49

> National Call Center for Homeless Veterans Find out how we can help you or a Veteran you care about connect with VA and local resources 24 hours a day , 7 days a week.

- [incorrect] t0124: National Call Center for Homeless Veterans (Service) -AVAILABLE_AT-> VA (Organization)
- [correct] t0125: National Call Center for Homeless Veterans (Service) -HAS_TIME_LIMIT-> 24 hours a day (TimeLimit)
- [correct] t0126: National Call Center for Homeless Veterans (Service) -HAS_TIME_LIMIT-> 7 days a week (TimeLimit)
- [correct] t0127: National Call Center for Homeless Veterans (Service) -APPLIES_TO-> Veteran you care about (Role)

### VA Housing Assistance | Veterans Affairs#1_0::5

> On this page Get VA Home Loan Benefits Get Veterans Housing Assistance Grants

- [incorrect] t0128: Veterans Housing Assistance (Service) -PART_OF-> Grants (Service)

### VA Housing Assistance | Veterans Affairs#1_0::51 (not extracted: short or boilerplate)

> Message us Ask a question online

- (no triples)

### VA Housing Assistance | Veterans Affairs#1_0::53

> Call us VA benefits hotline:800 - 827 - 1000 eBenefits technical support:800 - 983 - 0937 Call MyVA311 for help:844 - 698 - 2311 If you have hearing loss , call TTY : 711.

- (no triples)

### VA Housing Assistance | Veterans Affairs#1_0::60 (not extracted: short or boilerplate)

> Veterans Benefits Administration

- (no triples)

### VA Housing Assistance | Veterans Affairs#1_0::61

> Get updates Veterans benefits email updates

- [incorrect] t0129: Get updates (Service) -LEADS_TO-> Veterans benefits email updates (Service)

### VA Housing Assistance | Veterans Affairs#1_0::63

> Follow us Veterans Benefits Administration Facebook Veterans Benefits Administration Instagram Veterans Benefits Administration Linkedin Veterans Benefits Administration Twitter Veterans Benefits Administration YouTube

- [correct] t0130: Veterans Benefits Administration (Organization) -AVAILABLE_AT-> Facebook (ContactPoint)
- [correct] t0131: Veterans Benefits Administration (Organization) -AVAILABLE_AT-> Instagram (ContactPoint)
- [correct] t0132: Veterans Benefits Administration (Organization) -AVAILABLE_AT-> Linkedin (ContactPoint)
- [correct] t0133: Veterans Benefits Administration (Organization) -AVAILABLE_AT-> Twitter (ContactPoint)
- [correct] t0134: Veterans Benefits Administration (Organization) -AVAILABLE_AT-> YouTube (ContactPoint)

### VA Housing Assistance | Veterans Affairs#1_0::8

> How do I get help if I'm homeless or at risk of becoming homeless? We offer many programs and services that may help including free health care and, in some cases, free limited dental care. We can also help you connect with resources in your community, like homeless shelters or faith - based organizations. Find the support you need : Call the National Call Center for Homeless Veterans at 877 - 424 - 3838 for help 24 hours a day , 7 days a week. You ll talk privately with a trained VA counselor for free. Contact your nearest VA medical center and ask to talk with the VA social worker. If you're a female Veteran , ask for the Women Veterans Program Manager. Find the nearest VA medical center Talk with someone right now : If you're a Veteran in crisis or concerned about one , connect with our caring, qualified Veterans Crisis Line responders for confidential help. Many of them are Veterans themselves. This service is private, free, and available 24/7. Chat online with a trained VA staff member

- [correct] t0135: free health care (Service) -PROVIDED_BY-> VA medical center (Organization)
- [correct] t0136: free limited dental care (Service) -PROVIDED_BY-> VA medical center (Organization)
- [correct] t0137: National Call Center for Homeless Veterans (Organization) -AVAILABLE_AT-> 877 - 424 - 3838 (ContactPoint)
- [correct] t0138: Veterans Crisis Line (Service) -LEADS_TO-> confidential help (Outcome)
- [correct] t0139: Veterans Crisis Line (Service) -HAS_TIME_LIMIT-> 24/7 (TimeLimit)
- [incorrect] t0140: Chat online with a trained VA staff member (Service) -AVAILABLE_AT-> VA medical center (Organization)
