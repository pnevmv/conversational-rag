# Step 5: KG schema proposal (pilot open extraction)

Date: 2026-10-03 · Model: `gpt-5.4-nano-smirnov` (Azure OpenAI), temperature 0, strict JSON schema output

This report covers the first phase of KG construction: the structural layer in Neo4j, a pilot open extraction on 32 sections, and a proposed closed schema for full extraction. Nothing extracted by the LLM has been written to Neo4j yet.

## 1. Neo4j structural layer

**Setup.** Neo4j 5 Community runs in Docker (`docker compose up -d neo4j`, see `docker-compose.yml`). It was chosen over Aura Free because it runs locally, needs no account, and has no node limit. Aura Free caps a database at 200k nodes and 400k relationships; the structural layer alone uses about 40k nodes, before any extracted entities. Connection settings come from `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD` in `.env`. The client is `src/kg/client.py`.

**Ids.**
- `Section.section_id = "<doc_id>::<id_sp>"`, from `src.data.loader.make_section_id`. A RAG retrieval result's `(doc_id, id_sp)` therefore maps directly to a Section node.
- `Span.sp_id` uses the same form, so the dataset's grounding annotations `(doc_id, id_sp)` map directly to Span nodes.
- Uniqueness constraints exist on `Domain.name`, `Document.doc_id`, `Section.section_id` and `Span.sp_id`.

**Load.** `python -m src.kg.structure`. Every write uses MERGE on ids. Running the load twice gave identical counts.

| Label | Count |
|---|---:|
| Domain | 4 |
| Document | 488 |
| Section | 4,114 |
| Span | 35,659 |

| Relationship | Count |
|---|---:|
| HAS_DOCUMENT | 488 |
| HAS_SECTION | 4,114 |
| HAS_SPAN | 35,659 |
| NEXT | 3,626 (= 4,114 sections − 488 documents) |

## 2. Pilot extraction setup

- **Code:** `python -m src.kg.extract`. Output: `experiments/kg/pilot_open_extraction.jsonl`. Cache: `experiments/cache/kg_extract/`, keyed by SHA-256(section_id, prompt hash).
- **Sample:** 8 sections per domain, 32 in total, with `random.Random(42)`. Only content-bearing sections were eligible: at least 2 spans and at least 150 characters. This excludes the 57 heading-less and the many heading-only sections.
- **Prompt:** domain, document title, section heading and section text. It asks for open-typed entities `{name, type, evidence}` and relations `{source, relation, target, evidence}`, with evidence as a short verbatim quote.
- **Run:** 32/32 calls succeeded in about 30 s. A second run was served fully from the cache.
- **Output size:** 318 entities and 264 relations, with no empty sections. Per section, the median is 8 entities (range 4–30) and 6 relations (range 2–25).
- **Diversity:** there are 139 distinct entity types and 180 distinct relation types, typically about one per two mentions. Open extraction alone gives no usable schema.

Aggregates: `python -m src.kg.pilot_stats` writes `experiments/kg/pilot_stats.json`. The manual type mapping used in §5 is in `experiments/kg/pilot_type_mapping.json`.

## 3. Evidence check (hallucination signal)

Each evidence quote was checked against the section text in three ways:
- **Verbatim:** an exact substring after collapsing whitespace.
- **Near-verbatim:** a substring once case, punctuation and quote characters are ignored.
- **Not found:** neither of the above.

| | Verbatim | Near-verbatim | Not found | Total |
|---|---:|---:|---:|---:|
| Entities | 265 (83.3%) | 51 (16.0%) | 2 (0.6%) | 318 |
| Relations | 207 (78.4%) | 44 (16.7%) | 13 (4.9%) | 264 |
| **All** | **472 (81.1%)** | **95 (16.3%)** | **15 (2.6%)** | **582** |

Manual inspection of the 15 not-found quotes shows **no invented content**:

| Cause | n |
|---|---:|
| Fragments joined with "…" (each fragment is in the text) | 9 |
| List items stitched together without an ellipsis | 3 |
| A footnote marker ("3") inside the quote was dropped | 1 |
| Light paraphrase ("apply for" instead of "applying for") | 1 |
| Quote taken from the document title rather than the section text | 1 |

| Kind | Section | Item | Evidence |
|---|---|---|---|
| relation | Become a driving school instructor#3_0::10 | `Driving School Instructor -[REQUIRES_VISION_TEST]-> VisionT…` | “including must be at least 21 years of age ... a vision test” |
| relation | Become a driving school instructor#3_0::10 | `PreLicensingCourse -[REQUIRES_TEACHING_TECHNIQUES_COURSE]->…` | “If you want to teach the Pre - licensing Course , you must also successfully co…” |
| relation | Commercial vehicle registration fees, vehicle use taxe… | `AdditionalFee -[EXEMPTS]-> FarmRegistrationClass` | “The classes include ... Farm FAR” |
| relation | Commercial vehicle registration fees, vehicle use taxe… | `AdditionalFee -[EXEMPTS]-> HistoricalRegistrationClass` | “The classes include ... Historical HIS” |
| relation | Commercial vehicle registration fees, vehicle use taxe… | `AdditionalFee -[EXEMPTS]-> HouseTrailerRegistrationClass` | “The classes include ... House Trailer HOU” |
| relation | Commercial vehicle registration fees, vehicle use taxe… | `AdditionalFee -[EXEMPTS]-> SemiTrailerRegistrationClass` | “The classes include ... Semi Trailer SEM” |
| relation | Commercial vehicle registration fees, vehicle use taxe… | `AdditionalFee -[EXEMPTS]-> SpecialPurposeCommercialRegistra…` | “The classes include ... Special Purpose Commercial SPC” |
| relation | Commercial vehicle registration fees, vehicle use taxe… | `AdditionalFee -[EXEMPTS]-> TrailerRegistrationClass` | “The classes include ... Trailer TRL” |
| entity | Unpaid Refund Discharge \| Federal Student Aid#1_0::7 | `Unpaid Refund Discharge` | “"apply for an unpaid refund discharge"” |
| entity | Questions and Answers About FAFSA® Completion Data \| … | `FAFSACompletionData` | “Questions and Answers About FAFSA® Completion Data” |
| relation | VA Survivors Pension \| Veterans Affairs#1_0::1 | `VA Survivors Pension -[PAYS_TO]-> Unmarried Dependent Child…` | ““monthly payments to … unmarried dependent children”” |
| relation | VA Survivors Pension \| Veterans Affairs#1_0::1 | `Qualified Surviving Spouses -[ARE_RELATED_TO]-> Wartime Vet…` | ““qualified surviving spouses … of wartime Veterans”” |
| relation | VR&E Independent Living Track \| Veterans Affairs#1_0:… | `BenefitType -[INCLUDES]-> HomeConsultationsWithSpecialists` | “services may include : Home consultations with specialists” |
| relation | VR&E Independent Living Track \| Veterans Affairs#1_0:… | `BenefitType -[INCLUDES]-> ReferralToSupportResources` | “services may include : Referral to support resources” |
| relation | VR&E Independent Living Track \| Veterans Affairs#1_0:… | `BenefitType -[INCLUDES]-> EligibilityGuidanceForAdaptiveHou…` | “services may include : Guidance to help you understand if you re eligible for o…” |

**Caveat: a verbatim quote does not mean a correct triple.** All 20 `REQUIRES` relations were checked by hand:
- 13 are correct.
- 3 point the wrong way, e.g. `SupervisedDrivingPractice -[REQUIRES]-> RoadTest` and `VAHealthCareEligibilityCondition -[REQUIRES]-> VAHealthCare`.
- 4 are malformed, with a requirement node as the source, e.g. `DisabilityReviewRequirement -[REQUIRES]-> CaseReview`.

There are also 7 self-loops, e.g. `VA Health Care -[HAS_PDF]-> VA Health Care`. All relation endpoints match an extracted entity name (0 dangling).

## 4. Frequency tables

### 4.1 Entity types (count ≥ 3, with examples)

| Type | n | Maps to | Examples (name — evidence) |
|---|---:|---|---|
| EligibilityCondition | 29 | Requirement | `AgeRequirement` — “must be at least 21 years of age”<br>`ValidLicenseDurationRequirement` — “has been valid for at least 2 years preceding application”<br>`VehicleClassRequirement` — “in the class of vehicle that the instructor intends to teach in” |
| Service | 24 | Service | `SafetyInspection` — “When you need a safety inspection”<br>`RoadTest` — “before you take your road test”<br>`HazMat Endorsement` — “apply for a HazMat endorsement” |
| Document | 14 | Document | `ValidInspectionSticker` — “A valid inspection sticker must be displayed on your vehicle.”<br>`VehicleRegistrationSticker` — “"Your' registration' is the sticker placed on your windshield"”<br>`PaperRegistrationCertificate` — “"and the paper registration certificate that you must keep in your ve…” |
| Requirement | 11 | Requirement | `VehicleRegistrationAndTitleRequirement` — “"You or your business must register and title at a DMV office any veh…”<br>`SupervisedDrivingPractice` — “you must have supervised driving practice”<br>`AcceptableProofOfCitizenshipOrResidentStatus` — “HAZ-11 for a list of acceptable proof of citizenship or resident stat…” |
| Outcome | 11 | Outcome | `CombinationOfBenefits` — “he or she will get a combination of benefits that equals that higher …”<br>`SpouseSocialSecurityBenefitOnYourRecordMayBe…` — “his or her Social Security benefit on your record may be affected”<br>`BaseBenefitAmountForLife` — “The amount you receive when you first get benefits sets the base for …” |
| RegistrationClass | 8 | DROP:table-row category | `AgriculturalRegistrationClass` — “The classes include Agricultural AGR”<br>`AmbulanceRegistrationClass` — “Ambulance AMB”<br>`FarmRegistrationClass` — “Farm FAR” |
| PlateConfiguration | 8 | DROP:table-row category | `MedallionTaxiPlateConfigurationTnnnnnC` — “plate number configuration of " TnnnnnC "”<br>`MedallionTaxiPlateConfigurationTnnnnnnC` — “or " TnnnnnnC "”<br>`MedallionTaxiPlateConfigurationTnnnnnT` — “This tax does not include Medallion taxis with plate number configura…” |
| Program | 8 | Service | `CaseReview` — “we review your case from time to time to verify that you are still di…”<br>`Unpaid Refund Discharge` — “"apply for an unpaid refund discharge"”<br>`Closed School Discharge` — “"eligible for a closed school discharge"” |
| Benefit | 6 | Service | `SpouseRetirementBenefitsOnOwnRecord` — “retirement benefits on his or her own record”<br>`SpouseBenefitPayableOnYourRecord` — “the spouse benefit that is payable on your record”<br>`DisabilityBenefits` — “you will continue to receive benefits as long as you are disabled” |
| Agency | 5 | Agency | `Traffic Violations Bureau (TVB) (TVB)` — “schedule a hearing at a Traffic Violations Bureau TVB.”<br>`Department of Homeland Security (DHS)` — “permission to work from the Department of Homeland Security DHS”<br>`IRS` — “the IRS provides to us” |
| BenefitStartTiming | 5 | DROP:reified advice/statistic | `StartBenefitsBeforeFullRetirementAge` — “If you decide to start benefits : before your full retirement age , y…”<br>`StartBenefitsAtOrAfterFullRetirementAge` — “at your full retirement age or later , you will receive a larger mont…”<br>`DelayStartingBenefitsUntilFullRetirementAgeO…` — “you may want to delay starting your benefits until full retirement ag…” |
| Test | 4 | Service | `VisionTest` — “a vision test”<br>`RoadSignTest` — “road sign test”<br>`WrittenTest` — “written test” |
| Organization | 4 | Agency | `AutoDealer` — “"Auto dealers can register and title vehicles"”<br>`School` — “"contact that school"”<br>`Loan Servicer` — “"Contact your loan servicer for more information."” |
| FeeAmount | 4 | Fee | `FeeListedInChart` — “add 3.25% to the fee listed in the chart”<br>`Premium Amount` — “send you a letter with your premium amount”<br>`Income-Related Monthly Adjustment Amount` — “you ll pay an income - related monthly adjustment amount only on the …” |
| Process | 4 | Service | `Application Submission` — “you haven t submitted the application or correction yet”<br>`Correction Submission` — “you haven t submitted the application or correction yet”<br>`Qualification Determination` — ““Find out if you qualify and how to apply.”” |
| Office | 3 | Agency | `Traffic Violations Bureau (TVB) Office` — “At a TVB office You can plead to or pay a TVB ticket, and schedule a …”<br>`Regular DMV Issuing Office` — “You cannot plead to or pay a TVB ticket, or schedule a hearing at a r…”<br>`FinancialAidOffice` — “so that the financial aid office can subtract that amount” |
| Course | 3 | Service | `DriverTrainingAndTrafficSafetyCourse` — “complete a course in driver training and traffic safety, approved by …”<br>`PreLicensingCourse` — “If you want to teach the Pre - licensing Course”<br>`TeachingTechniquesAndMethodologyCourse` — “successfully complete a 30-hour Teaching Techniques and Methodology c…” |
| TimePeriod | 3 | TimeLimit | `InspectionFrequency` — “every 12 months”<br>`SupportHours` — “from 8:00 a.m. to 5:30 p.m., Monday through Friday.”<br>`ServiceDuration` — “These services generally last up to 24 months.” |
| InformationPage | 3 | NEW:ContactPoint | `VehiclePlatesInformation` — “"See information about vehicle plates"”<br>`VehicleTitlesInformation` — “"or vehicle titles"”<br>`Medical Certification Requirements` — “See Medical Certification Requirements [5] for more information.” |
| Fee | 3 | Fee | `DealerFee` — “"and charge a fee for this."”<br>`SupplementalFee` — “The chart show the use taxes and supplemental fees”<br>`AdditionalFee` — “Several registration classes are exempt from the additional fee” |
| Form | 3 | Document | `MV-15FOIL` — “Permissible uses are listed on Page 2 of the MV-15FOIL”<br>`Loan Discharge Application: Unpaid Refund` — “"complete the Loan Discharge Application: Unpaid Refund"”<br>`FAFSA Form` — “into the FAFSA form via the IRS DRT” |
| DocumentRequirement | 3 | Requirement | `OriginalDocuments` — “You must present original documents or copies certified by the agency…”<br>`CertifiedCopies` — “You must present original documents or copies certified by the agency…”<br>`CurrentNotExpiredDocuments` — “All documents must be current not expired” |
| DocumentRestriction | 3 | Requirement | `NoPhotocopies` — “We cannot accept photocopies or notarized copies”<br>`NoNotarizedCopies` — “We cannot accept photocopies or notarized copies”<br>`NoReceiptForDocumentApplication` — “We cannot accept a receipt showing you applied for the document” |
| Consequence | 3 | Outcome | `GiveUpSomeBenefitsDueToEarnings` — “Depending on the amount of your benefit and your earnings for the yea…”<br>`LosePaycheckIfStopWorking` — “If you stop working , not only will you lose your paycheck”<br>`LoseEmployerProvidedHealthInsuranceIfStopWor…` — “but you may also lose valuable employer provided health insurance.” |
| HealthCoverageOption | 3 | Service | `MedicareAtAge65` — “You can apply for just Medicare at age 65 and start receiving retirem…”<br>`ExtendHealthInsuranceCoverageAfterRetire` — “or if you can temporarily extend your health insurance coverage after…”<br>`SwitchToSpouseHealthInsurance` — “if you are married and your spouse is employed , you may be able to s…” |
| LoanProgram | 3 | Service | `DirectLoans` — “General forbearances are available for Direct Loans, Federal Family E…”<br>`FederalFamilyEducationFFELProgramLoans` — “General forbearances are available for Direct Loans, Federal Family E…”<br>`PerkinsLoans` — “General forbearances are available for Direct Loans, Federal Family E…” |
| Place | 3 | DROP:place/jurisdiction (-> property) | `NewYorkCity` — “adding up all the applications reported under " New York City "”<br>`Queens` — “would exclude any institutions reported being within " Queens "”<br>`Jamaica` — “or even within " Jamaica, " a smaller neighborhood within the New Yor…” |
| Role | 3 | Role | `School Certifying Official` — ““You should contact your school s certifying official to make sure yo…”<br>`VocationalRehabilitationCounselor (VRC)` — “"Your Vocational Rehabilitation Counselor VRC can provide"”<br>`VeteranWoman` — ““As a woman Veteran , you re part of the fastest - growing group”” |

**Long tail (count < 3, 111 types):** Regulation (2), Certificate (2), CourseDuration (2), CitizenshipStatus (2), TransactionType (2), Website (2), Amount (2), Circumstance (2), PhoneNumber (2), IncomeComponent (2), FilingStatus (2), MedicareProgram (2), PolicyConsequence (2), EarningsLimit (2), RecalculationProcess (2), LifeExpectancy (2), LifeExpectancyStatistic (2), Action (2), Device (2), CalculationQuestion (2), LocationConcept (2), DataAvailabilityCondition (2), EligibilityGroup (2), Ticket (1), Hearing (1), ServiceOrRole (1), AgencyOrOrganization (1), GovernmentAgency (1), Provider (1), CourseLevel (1), LocationType (1), TriggerCondition (1), DeadlineRule (1), AgencyOffice (1), Vehicle (1), CourseRequirement (1), Restriction (1), TimeRequirement (1), PDFDocument (1), BackgroundCheckRequirement (1), Instruction (1), ServiceInformation (1), Tax (1), TaxRate (1), Jurisdiction (1), RoundingRule (1), VehicleType (1), NotationRule (1), Pension (1), ApplicantType (1), Deadline (1), Application (1), Account (1), PolicyLimit (1), BenefitAmountRule (1), Limit (1), BenefitAmountRange (1), ReductionRule (1), OutcomeRule (1), ServiceOutcome (1), CalculationMethod (1), IncomeMeasure (1), Notice (1), Reason (1), AdministrativeAction (1), DecisionFactor (1), AgeThreshold (1), BenefitAmount (1), Notification (1), PlanningGuideline (1), FinancialNeed (1), RiskFactor (1), EmployerBenefit (1), ForbearanceProgram (1), UserGroup (1), InterfaceElement (1), RolloutPlan (1), CompetenceRequirement (1), EvaluationStandard (1), EvaluationMethod (1), CompetencyArea (1), AlignmentRequirement (1), DevelopmentRequirement (1), InformationRequirement (1), UniformApplicationRequirement (1), ConsiderationRule (1), PublicAccessRequirement (1), Button (1), QualityClaim (1), ExpenseCategory (1), DataSet (1), ApplicationCountCondition (1), Cause (1), Consideration (1), Scholarship (1), StudentAid (1), Cost (1), AidType (1), FinancialAid (1), VeteranDesignation (1), Condition (1), Law (1), PersonRole (1), ProtectionOutcome (1), AccommodationOutcome (1), Example (1), PaymentType (1), BeneficiaryGroup (1), GoverningBody (1), ServiceCategory (1), Grant (1)

### 4.2 Relation types (count ≥ 2, with examples)

| Relation | n | Maps to | Examples (triple — evidence) |
|---|---:|---|---|
| REQUIRES | 20 | REQUIRES | `VehicleRegistrationInNewYorkState -[REQUIRES]-> SafetyInspection` — “All vehicles registered in New York State must get a safety…”<br>`SafetyInspection -[REQUIRES]-> ValidInspectionSticker` — “A valid inspection sticker must be displayed on your vehicl…”<br>`SupervisedDrivingPractice -[REQUIRES]-> RoadTest` — “you must have supervised driving practice” |
| EXEMPTS | 8 | EXEMPT_FROM (inverse) | `AdditionalFee -[EXEMPTS]-> AgriculturalRegistrationClass` — “Several registration classes are exempt from the additional…”<br>`AdditionalFee -[EXEMPTS]-> AmbulanceRegistrationClass` — “The classes include Agricultural AGR, Ambulance AMB”<br>`AdditionalFee -[EXEMPTS]-> FarmRegistrationClass` — “The classes include ... Farm FAR” |
| INCLUDES | 7 | NEW:PART_OF (inverse) | `Premium Determination Letter -[INCLUDES]-> Premium Amount` — “send you a letter with your premium amount”<br>`Premium Determination Letter -[INCLUDES]-> Reason for Determination` — “and the reason for our determination”<br>`VA Survivors Pension -[INCLUDES]-> Application Process` — ““and how to apply.”” |
| NOT_INCLUDED_FOR_PLATE_CONFIGURATION | 6 | EXEMPT_FROM (inverse) | `MedallionTaxi -[NOT_INCLUDED_FOR_PLATE_CONFIGURATION]-> MedallionTaxi…` — “This tax does not include Medallion taxis with plate number…”<br>`MedallionTaxi -[NOT_INCLUDED_FOR_PLATE_CONFIGURATION]-> MedallionTaxi…` — “" TnnnnnnT "”<br>`MedallionTaxi -[NOT_INCLUDED_FOR_PLATE_CONFIGURATION]-> MedallionTaxi…` — “" nana "” |
| APPLIES_TO | 5 | APPLIES_TO | `CountyUseTaxChart -[APPLIES_TO]-> OriginalRegistration` — “for all original registrations and renewals”<br>`CountyUseTaxChart -[APPLIES_TO]-> Renewal` — “for all original registrations and renewals”<br>`ApplicationWithdrawal -[APPLIES_TO]-> SocialSecurityRetirementApplica…` — “Learn more about Withdrawing Your Social Security Retiremen…” |
| BASED_ON | 4 | NEW:DETERMINED_BY | `MonthlyBenefitUpTo50Percent -[BASED_ON]-> MaximumFamilyAmount` — “Each family member may be eligible for a monthly benefit of…”<br>`Higher Medicare Premiums -[BASED_ON]-> Modified Adjusted Gross Income…` — “based on your modified adjusted gross income MAGI”<br>`DemonstrateCompetenceInAcademicSubjects -[BASED_ON]-> HighObjectiveUn…` — “based on a high, objective, uniform state standard of evalu…” |
| RESULTS_IN | 4 | LEADS_TO | `StartBenefitsBeforeFullRetirementAge -[RESULTS_IN]-> MonthlyBenefitAm…` — “If you decide to start benefits : before your full retireme…”<br>`StartBenefitsAtOrAfterFullRetirementAge -[RESULTS_IN]-> MonthlyBenefi…` — “at your full retirement age or later , you will receive a l…”<br>`CheckAdditionalEarningsIncrease -[RESULTS_IN]-> SSARecalculatedBenefi…` — “If they do , we will send you a letter telling you your new…” |
| HAS_PDF | 4 | NEW:AVAILABLE_AT | `VA Health Care -[HAS_PDF]-> VA Health Care` — “Apply for VA health care PDF”<br>`Mental Health Services -[HAS_PDF]-> Mental Health Services` — “Get started with mental health services PDF”<br>`Disability Rating -[HAS_PDF]-> Disability Rating` — “Apply for a disability rating PDF” |
| REJECTS | 3 | REQUIRES | `Social Security Number -[REJECTS]-> NoPhotocopies` — “We cannot accept photocopies or notarized copies”<br>`Social Security Number -[REJECTS]-> NoNotarizedCopies` — “We cannot accept photocopies or notarized copies”<br>`Social Security Number -[REJECTS]-> NoReceiptForDocumentApplication` — “We cannot accept a receipt showing you applied for the docu…” |
| AVAILABLE_FOR | 3 | APPLIES_TO | `GeneralForbearance -[AVAILABLE_FOR]-> DirectLoans` — “General forbearances are available for Direct Loans, Federa…”<br>`GeneralForbearance -[AVAILABLE_FOR]-> FederalFamilyEducationFFELProgr…` — “General forbearances are available for Direct Loans, Federa…”<br>`GeneralForbearance -[AVAILABLE_FOR]-> PerkinsLoans` — “General forbearances are available for Direct Loans, Federa…” |
| SET_BY | 3 | PROVIDED_BY | `HighObjectiveUniformStateStandardOfEvaluation -[SET_BY]-> StateSetsUn…` — “The uniform state standard of evaluation may involve multip…”<br>`Income Limits -[SET_BY]-> Congress` — ““limits set by Congress””<br>`Net Worth Limits -[SET_BY]-> Congress` — ““limits set by Congress”” |
| PROVIDES | 3 | PROVIDED_BY (inverse) | `HighObjectiveUniformStateStandardOfEvaluation -[PROVIDES]-> Objective…` — “provide objective, coherent information about your attainme…”<br>`VocationalRehabilitationCounselor (VRC) -[PROVIDES]-> RehabilitationS…` — “"can provide a full range of rehabilitation services"”<br>`VA Survivors Pension -[PROVIDES]-> Monthly Payments` — ““VA Survivors Pension offers monthly payments”” |
| IS_PART_OF | 2 | NEW:PART_OF | `Traffic Violations Bureau (TVB) Office -[IS_PART_OF]-> Traffic Violat…` — “schedule a hearing at a Traffic Violations Bureau TVB.”<br>`WomenHealthServices -[IS_PART_OF]-> BenefitsAccess` — ““as part of your benefits”” |
| TRIGGERED_BY | 2 | LEADS_TO (inverse) | `SafetyInspection -[TRIGGERED_BY]-> OwnershipTransfer` — “every 12 months when the ownership of the vehicle is transf…”<br>`Higher Medicare Premiums -[TRIGGERED_BY]-> Premium Determination Lett…` — “If you must pay higher premiums , we ll send you a letter w…” |
| STATES_NOT_REQUIRED | 2 | EXEMPT_FROM | `RegistrationNotOwnerNameRequirement -[STATES_NOT_REQUIRED]-> DMVOffice` — “"Registrations do not need to be in the owner's name"”<br>`RegistrationNotSinglePersonRequirement -[STATES_NOT_REQUIRED]-> DMVOf…` — “"or for only one person."” |
| REFERENCES | 2 | DROP | `VehiclePlatesInformation -[REFERENCES]-> VehiclePlates` — “"See information about vehicle plates"”<br>`VehicleTitlesInformation -[REFERENCES]-> VehicleTitle` — “"See information about vehicle plates [1] or vehicle titles…” |
| SHOWS | 2 | DROP | `CountyUseTaxChart -[SHOWS]-> UseTax` — “The chart show the use taxes and supplemental fees”<br>`CountyUseTaxChart -[SHOWS]-> SupplementalFee` — “The chart show the use taxes and supplemental fees” |
| DEPENDS_ON | 2 | NEW:DETERMINED_BY | `SalesTaxRate -[DEPENDS_ON]-> PurchasePrice` — “The amount of the sales tax depends on the purchase price a…”<br>`SalesTaxRate -[DEPENDS_ON]-> Locality` — “The amount of the sales tax depends on the purchase price a…” |
| SUBJECT_TO_TAX_FOR_PLATE_CONFIGURATION | 2 | HAS_FEE | `MedallionTaxi -[SUBJECT_TO_TAX_FOR_PLATE_CONFIGURATION]-> MedallionTa…` — “This tax applies to Medallion taxis with a plate number con…”<br>`MedallionTaxi -[SUBJECT_TO_TAX_FOR_PLATE_CONFIGURATION]-> MedallionTa…` — “or " TnnnnnnC "” |
| AFFECTS | 2 | LEADS_TO | `SpouseReceivesPensionNotCoveredBySocialSecurity -[AFFECTS]-> SpouseSo…` — “his or her Social Security benefit on your record may be af…”<br>`Scholarship -[AFFECTS]-> OtherStudentAid` — “A scholarship will affect your other student aid” |
| MAY_CHANGE_DUE_TO | 2 | NEW:DETERMINED_BY | `ContinuingEligibilityForDisabilityBenefits -[MAY_CHANGE_DUE_TO]-> Hea…` — “your health may improve to the point where you are no longe…”<br>`ContinuingEligibilityForDisabilityBenefits -[MAY_CHANGE_DUE_TO]-> Ret…` — “or you go back to work” |
| REQUIRES_ORIGINAL_OR_CERTIFIED_DOCUMENTS | 2 | REQUIRES | `Social Security Number -[REQUIRES_ORIGINAL_OR_CERTIFIED_DOCUMENTS]-> …` — “You must present original documents or copies certified by …”<br>`Social Security Number -[REQUIRES_ORIGINAL_OR_CERTIFIED_DOCUMENTS]-> …` — “You must present original documents or copies certified by …” |
| IS_COMPOSED_OF | 2 | NEW:PART_OF (inverse) | `Modified Adjusted Gross Income (MAGI) -[IS_COMPOSED_OF]-> Adjusted Gr…` — “Your MAGI is your total adjusted gross income”<br>`Modified Adjusted Gross Income (MAGI) -[IS_COMPOSED_OF]-> Tax-Exempt …` — “and tax - exempt interest income” |
| REQUIRES_MAGI_GREATER_THAN | 2 | REQUIRES | `Higher Medicare Premiums -[REQUIRES_MAGI_GREATER_THAN]-> MAGI Thresho…` — “If you file your taxes as married, filing jointly and your …”<br>`Higher Medicare Premiums -[REQUIRES_MAGI_GREATER_THAN]-> MAGI Thresho…` — “If you file your taxes using a different status, and your M…” |
| PAID_ON | 2 | DROP | `Income-Related Monthly Adjustment Amount -[PAID_ON]-> Part B` — “If you have only one Medicare Part B or Medicare prescripti…”<br>`Income-Related Monthly Adjustment Amount -[PAID_ON]-> Medicare Prescr…` — “If you have only one Medicare Part B or Medicare prescripti…” |
| APPLIES_WHEN | 2 | REQUIRES | `Automatic Adjustment to Other Program -[APPLIES_WHEN]-> Automatic Adj…` — “we ll apply an adjustment automatically to the other progra…”<br>`WithholdingTotalsOrSchoolNames -[APPLIES_WHEN]-> FewerThanFiveComplet…` — “impact of withholding the totals or names of schools with f…” |
| CONDITIONED_ON | 2 | REQUIRES | `Law Does Not Apply If Income Not Greater Than Limits -[CONDITIONED_ON…` — “if your income isn t greater than the limits described abov…”<br>`SwitchToSpouseHealthInsurance -[CONDITIONED_ON]-> LoseEmployerProvide…` — “if you are married and your spouse is employed , you may be…” |
| DIFFERS_BY | 2 | NEW:DETERMINED_BY | `MonthlyBenefitAmount -[DIFFERS_BY]-> StartBenefitsBeforeFullRetiremen…` — “Your monthly benefit amount can differ substantially based …”<br>`MonthlyBenefitAmount -[DIFFERS_BY]-> StartBenefitsAtOrAfterFullRetire…` — “Your monthly benefit amount can differ substantially based …” |
| SUPPORTS_CONSIDERATION_OF | 2 | DROP | `ProbabilityLivePastAge90 -[SUPPORTS_CONSIDERATION_OF]-> DelayStarting…` — “About one out of every four 65-year - olds today will live …”<br>`ProbabilityLivePastAge95 -[SUPPORTS_CONSIDERATION_OF]-> DelayStarting…` — “One out of 10 will live past age 95.” |
| BASED_ON_FAMILY_HISTORY | 2 | NEW:DETERMINED_BY | `DelayStartingBenefitsUntilFullRetirementAgeOrLater -[BASED_ON_FAMILY_…` — “If the answer is yes, and you have every reason to believe …”<br>`StartBenefitsEarlierIfFamilyNotLongLived -[BASED_ON_FAMILY_HISTORY]->…` — “If they didn't , you may choose to start receiving retireme…” |
| RELATED_TO | 2 | DROP | `NeedExtraMoneyInLaterYears -[RELATED_TO]-> OutlivePensionsOrAnnuities…` — “particularly if you may outlive pensions or annuities with …”<br>`AdaptiveHousingPrograms -[RELATED_TO]-> AdaptiveHousingGrants` — “Learn more about adaptive housing grants” |
| LOCATED_ON | 2 | NEW:AVAILABLE_AT | `Aidan Owl Icon -[LOCATED_ON]-> Desktop Device` — “look for the Aidan owl icon in the bottom right - hand corn…”<br>`Aidan Owl Icon -[LOCATED_ON]-> Mobile Device` — “look for the Aidan owl icon in the bottom right - hand corn…” |
| AVAILABLE_IF_NOT_SUBMITTED | 2 | REQUIRES | `Reset FAFSA Button -[AVAILABLE_IF_NOT_SUBMITTED]-> Application Submis…` — “If , despite this , you still want to clear the information…”<br>`Reset FAFSA Button -[AVAILABLE_IF_NOT_SUBMITTED]-> Correction Submiss…` — “and you haven t submitted the application or correction yet…” |
| ANSWERED_NO | 2 | DROP | `StateTotalCalculation -[ANSWERED_NO]-> FAFSACompletionData` — “The answer to both questions is no.”<br>`CityTotalCalculation -[ANSWERED_NO]-> FAFSACompletionData` — “The answer to both questions is no.” |
| SUBTRACTS_FROM | 2 | DROP | `FinancialAidOffice -[SUBTRACTS_FROM]-> CostOfAttendance` — “financial aid office can subtract that amount from your cos…”<br>`FinancialAidOffice -[SUBTRACTS_FROM]-> Loans` — “subtract that amount from your cost of attendance and from …” |
| QUALIFIES_FOR | 2 | APPLIES_TO (inverse) | `ServiceConnectedDisability -[QUALIFIES_FOR]-> VocationalRehabilitatio…` — “"If you re a Veteran with a service - connected disability …”<br>`VeteranWoman -[QUALIFIES_FOR]-> VAHealthCareEligibilityCondition` — ““As a woman Veteran , you re part of the fastest - growing …” |
| PAYS_TO | 2 | APPLIES_TO | `VA Survivors Pension -[PAYS_TO]-> Qualified Surviving Spouses` — ““monthly payments to qualified surviving spouses””<br>`VA Survivors Pension -[PAYS_TO]-> Unmarried Dependent Children` — ““monthly payments to … unmarried dependent children”” |
| ARE_RELATED_TO | 2 | DROP | `Qualified Surviving Spouses -[ARE_RELATED_TO]-> Wartime Veterans` — ““qualified surviving spouses … of wartime Veterans””<br>`Unmarried Dependent Children -[ARE_RELATED_TO]-> Wartime Veterans` — ““unmarried dependent children of wartime Veterans”” |

**Long tail (count 1, 142 types):** ALLOWS_PLEAD_OR_PAY, ALLOWS_SCHEDULE_HEARING, PROHIBITS_PLEAD_OR_PAY, PROHIBITS_SCHEDULE_HEARING, REQUIRES_EMPLOYMENT_BY, LICENSED_BY, GOVERNED_BY_REGULATION, REQUIRES_AGE_AT_LEAST, REQUIRES_VALID_FOR_AT_LEAST, REQUIRES_VALID_FOR_VEHICLE_CLASS, REQUIRES_NO_SUSPENSION_OR_REVOCATION, REQUIRES_ACCEPTABLE_DRIVING_RECORD, REQUIRES_HIGH_SCHOOL_OR_EQUIVALENCY_DIPLOMA, REQUIRES_VISION_TEST, REQUIRES_ROAD_SIGN_TEST, REQUIRES_WRITTEN_TEST, REQUIRES_DRIVING_TEST, REQUIRES_NO_CONVICTION_OF_CERTAIN_CRIMES, RENEWAL_REQUIRES_COURSE, REQUIRES_AT_LEAST_DURATION, TAUGHT_BY, REQUIRES_TEACHING_TECHNIQUES_COURSE, HAS_DURATION, IS_COLLEGE_LEVEL, REQUIRES_BEHIND_THE_WHEEL_EXPERIENCE, DONE_AT, REQUIRED_EVERY, EXPIRES_BY_RULE, IS_STICKER_ON, MUST_BE_KEPT_IN, APPLIES_AT, REQUIRES_REGISTRATION_AND_TITLE_OF, CAN_PERFORM, ISSUES, CHARGES_FEE, REQUIRES_FOLLOWING, GOVERNS_SCHEDULING_FOR, LISTS, PROVIDES_MORE_INFORMATION_ON, REQUIRES_DOCUMENT, LISTED_ON, ALLOWS_ACTION, OBTAINED_FROM, USED_TO_CALCULATE, DEFINES, PAID_FIRST, MAY_RESULT_IN, EQUALS, INCLUDES_EXAMPLE, CONTINUES_AS_LONG_AS, VERIFIES, PROVIDES_UPDATES_ON, REQUIRES_PERMISSION_TO_WORK_FROM, REQUIRES_ELIGIBILITY_FOR_NONCITIZEN_ADULT, REQUIRES_CURRENT_NOT_EXPIRED_DOCUMENTS, ALLOWS_WITHDRAWAL_UNTIL, REQUIRES_REPAYMENT_OF, CHECKS_STATUS_USING, AVAILABLE_AT, USES_PHONE_NUMBER, USES_TTY_NUMBER, LIMITS, GENERALLY_BETWEEN, APPLIES_IF_EXCEEDS, NOT_AFFECTED_BY, CALCULATED_BY, PROVIDED_BY, DETERMINED_USING, RESULT_OF, INFORMS_DECISION_BY, SETS_BASE_FOR, APPLIES_BETWEEN, MAY_CAUSE, HAS_NO_EARNINGS_LIMIT, TRIGGERS, PROVIDES_CREDIT_FOR, ALLOWS, ADVISED_BY, BASED_ON_HEALTH, CO-OCCURS_WITH, LIMITS_COVERAGE_UNTIL, INFORMS, REQUIRES_CONTACT_BEFORE_APPLYING, REQUIRES_CHECK_CLOSED_SCHOOL_DISCHARGE_ELIGIBILITY, CONTACTS_FOR_INFORMATION, IDENTIFIED_VIA, REQUIRES_COMPLETING_FORM, SENT_TO, AVAILABLE_TO, REQUIRES_LOGIN_TO_ACCESS, DISPLAYS_ICON_FOR, ABSENCE_MEANS_CHECK_BACK, ALTERNATIVELY_REQUIRES, MAY_INVOLVE, COVERS, ALIGNED_WITH, DEVELOPED_IN_CONSULTATION_WITH, APPLIED_UNIFORMLY, CONSIDERS_BUT_NOT_BASED_PRIMARILY_ON, MADE_AVAILABLE_TO_PUBLIC_UPON_REQUEST, TRANSFERS_INFORMATION_TO, ALTERNATIVE_TO, DISCOURAGES_CLEARING, IS_FASTEST_AND_MOST_ACCURATE, MAY_REDUCE_PAPERWORK, CLEARS_APPLICATION_OR_CORRECTION, REQUIRES_STARTING_OVER, ALLOWS_UP_TO, FUNDS, FOR_SCHOOLS_AT_LEVELS, MAY_BE_SUBURB_WITHIN, EXCLUDES_QUEENS, EXCLUDES_JAMAICA, CANNOT_ASSUME_ZERO, RESULT_OF_SUMMING_FILES, CAUSED_BY, REQUIRES_CONSIDERATION_OF, CAPPED_BY, INFORMED_TO, COVERS_REMAINING_AMOUNT, PRINTED_ON, MAY_ENABLE, MAY_REQUIRE, CHECK_WITH, VARIES_BY, HELPS_PICK, CONFIRMS_APPROVAL_FOR, PROTECTED_UNDER, PREVENTS_DISADVANTAGE_IN, HELPS_EMPLOYER_ACCOMMODATE, REFERS_TO, HELPS_RETURN_TO, SUPPORTS, PROVIDES_ACCESS_TO, CALCULATED_USING, AVAILABLE_AS, SPLIT_INTO, INVITES, GUIDES_ELIGIBILITY_FOR, ENABLES_HOME_CHANGES, GENERALLY_LAST_UP_TO, CAN_BE_EXTENDED_IN_SOME_CASES

## 5. Mapping onto the candidate schema

Every open type was assigned by hand to a candidate type, a new type, or DROP (`pilot_type_mapping.json`).

### 5.1 Entities (318 mentions)

| Candidate type | Mentions | Open types merged into it |
|---|---:|---|
| Service | 73 | Service, Program, Benefit, Test, Process, Course, LoanProgram, HealthCoverageOption, MedicareProgram, Grant, Scholarship, … (22 types) |
| Requirement | 63 | EligibilityCondition (29), Requirement (11), DocumentRequirement, DocumentRestriction, Restriction, TriggerCondition, Circumstance, AgeThreshold, … (20 types) |
| Document | 26 | Document, Form, Certificate, Ticket, PDFDocument, Notice, Notification, Application, … (10 types) |
| Outcome | 22 | Outcome, Consequence, PolicyConsequence, ServiceOutcome, ReductionRule, … (9 types) |
| Fee | 19 | FeeAmount, Fee, Amount, Tax, TaxRate, EarningsLimit, BenefitAmount, Cost, Limit, … (12 types) |
| Agency | 18 | Agency, Organization, Office, GovernmentAgency, Provider, GoverningBody, … (9 types) |
| Role | 14 | Role, EligibilityGroup, BeneficiaryGroup, ApplicantType, CitizenshipStatus, FilingStatus, … (9 types) |
| TimeLimit | 8 | TimePeriod, CourseDuration, Deadline, DeadlineRule, TimeRequirement |
| **Candidate total** | **243 (76.4%)** | |
| *Missing:* ContactPoint | 8 (2.5%) | InformationPage, Website, PhoneNumber, Account |
| *Drop* | 67 (21.1%) | see below |

**What fits:**
- **Requirement, Service, Document:** these 3 types cover 162 mentions (51%). Requirement and Service hold up in every domain.
- **Role and Outcome:** these fit, but Outcome is the noisiest type. It is often a whole proposition turned into a node, e.g. `SpouseSocialSecurityBenefitOnYourRecordMayBeAffected`.

**What doesn't fit well:**
- **Agency is too narrow.** 7 of its 18 mentions are not government agencies: schools, loan servicers, auto dealers, DMV offices and inspection stations. The type should be **Organization**, with a `kind` property.
- **Fee is too narrow.** Only 6 of its 19 mentions are fees or taxes. The rest are premiums, benefit amounts, earnings limits and costs, which are amounts a citizen asks about just as often ("how much will I get?"). The type should be **Amount**.
- **Fee and TimeLimit lose the value itself.** Only 2 of 19 amount entities have a number in their name, against 5 in their evidence. TimeLimit names look like `InspectionFrequency` while the evidence says "every 12 months". These types need a verbatim `value` property, or they cannot answer "how much / how long" questions.
- **TimeLimit is rare (8 mentions)** but central to MultiDoc2Dial questions. The pilot sample is small, so it should stay.

**Missing:**
- **ContactPoint:** phone numbers, websites, online accounts and information pages. These are rare in the pilot (8 mentions), but MultiDoc2Dial agent turns often point the user to a phone number, office or website ("call…", "visit…", "log in to…"). Without this type, those answers have nowhere to attach.

**Drop (67 mentions):**

| Reason | n | Examples |
|---|---:|---|
| Table-row categories | 19 | RegistrationClass (8), PlateConfiguration (8): *all* 16 come from one DMV fee-table section (`…supplemental fees#3_0::34`) |
| UI or meta content | 17 | Button, Device, InterfaceElement, QualityClaim, CalculationQuestion, Example |
| Reified advice or statistics | 13 | BenefitStartTiming, LifeExpectancy, RiskFactor, PlanningGuideline |
| Calculation details | 8 | IncomeComponent, RoundingRule, NotationRule, CalculationMethod |
| Places, jurisdictions | 7 | Place (NYC, Queens, Jamaica): better as a `jurisdiction` property |
| Legal references | 3 | Regulation, Law: better as a `legal_basis` property |

### 5.2 Relations (264 mentions)

| Candidate relation | Mentions (same direction + inverse) | Main open types merged into it |
|---|---:|---|
| REQUIRES | 63 + 0 | REQUIRES (20), REQUIRES_* variants (~30), CONDITIONED_ON, APPLIES_WHEN, REJECTS |
| LEADS_TO | 17 + 4 | RESULTS_IN, AFFECTS, MAY_RESULT_IN, TRIGGERS · inverse: TRIGGERED_BY, CAUSED_BY, RESULT_OF |
| EXEMPT_FROM | 4 + 14 | STATES_NOT_REQUIRED, NOT_AFFECTED_BY · inverse: EXEMPTS (8), NOT_INCLUDED_FOR_… (6), all from the fee-table section |
| APPLIES_TO | 14 + 2 | APPLIES_TO, AVAILABLE_FOR, PAYS_TO, AVAILABLE_TO, COVERS · inverse: QUALIFIES_FOR |
| PROVIDED_BY | 7 + 6 | SET_BY, LICENSED_BY, TAUGHT_BY, OBTAINED_FROM · inverse: PROVIDES, ISSUES, FUNDS |
| HAS_DEADLINE | 9 + 0 | HAS_DURATION, REQUIRED_EVERY, ALLOWS_WITHDRAWAL_UNTIL, GENERALLY_LAST_UP_TO |
| HAS_FEE | 7 + 0 | CHARGES_FEE, SUBJECT_TO_TAX_…, CAPPED_BY, ALLOWS_UP_TO, GENERALLY_BETWEEN |
| ALTERNATIVE_TO | 3 + 0 | ALTERNATIVE_TO, ALTERNATIVELY_REQUIRES, REQUIRES_CHECK_CLOSED_SCHOOL_DISCHARGE_ELIGIBILITY |
| **Candidate total** | **150 (56.8%)** | 26 of these are extracted in the inverse direction |
| *Missing:* DETERMINED_BY | 18 + 2 | BASED_ON, DEPENDS_ON, VARIES_BY, DIFFERS_BY, CALCULATED_USING |
| *Missing:* AVAILABLE_AT | 16 + 2 | HAS_PDF, USES_PHONE_NUMBER, DONE_AT, CHECK_WITH, CONTACTS_FOR_INFORMATION |
| *Missing:* PART_OF | 2 + 11 | IS_PART_OF · inverse: INCLUDES (7), IS_COMPOSED_OF, SPLIT_INTO |
| *Drop* | 63 (23.9%) | REFERENCES, SHOWS, RELATED_TO, ANSWERED_NO, DISPLAYS_ICON_FOR, … (55 types) |

**Observations:**
- **REQUIRES dominates.** About 24% of relations are requirements once the ~30 `REQUIRES_<OBJECT>` variants are folded in. The model encodes the target in the relation name (`REQUIRES_VISION_TEST`), so the closed schema must forbid this.
- **Direction is unstable.** 41 of 264 relations (15.5%) express a schema relation in the inverse direction (EXEMPTS vs EXEMPT_FROM, INCLUDES vs PART_OF, PROVIDES vs PROVIDED_BY). The closed prompt must fix direction with explicit domain → range definitions.
- **EXEMPT_FROM looks frequent only because of one section.** 14 of its 18 mentions come from the fee-table section, so it is rare elsewhere. It stays because exemption questions ("do I need X if …") are a typical MultiDoc2Dial pattern.
- **HAS_FEE and HAS_DEADLINE are rare (7 and 9).** Their range types are rare too, and the same sample-size caveat as for TimeLimit applies.
- **ALTERNATIVE_TO is rare (3)** but carries a dialogue-critical pattern: "if the school has closed, you may be eligible for a closed school discharge *instead*". It stays.
- **The dropped quarter is mostly discourse or UI.** Examples: `ANSWERED_NO`, `DISPLAYS_ICON_FOR`, `IS_FASTEST_AND_MOST_ACCURATE`, and vague `RELATED_TO`/`REFERENCES`.

## 6. Other findings that affect full extraction

1. **Names are identifiers, not mentions.** 218 of 318 entity names (69%) are CamelCase identifiers (`NoSuspensionOrRevocationLast2YearsRequirement`) rather than the surface form. The cause is the prompt's CamelCase instruction for *types*, which leaked into names. This hurts entity resolution and linking back to text. Fix: require `name` to be the shortest verbatim noun phrase from the text.
2. **Propositions become nodes.** Many Requirement and Outcome entities are whole clauses. This is acceptable for Requirement, where the clause *is* the condition, but such nodes should keep a verbatim `text` and a short `name`.
3. **Very little cross-section overlap in the pilot.** Only 2 names repeat across sections (`PreLicensingCourse`, `School`). The 32 sections come from 31 different documents, so entity resolution cannot be judged from this pilot. It needs a test on whole documents.
4. **Tables extract poorly.** The one fee-table section produced 30 entities and 25 relations: 9% of all entities from 3% of sections, almost all of it row-level noise. Table-like sections should be capped or summarised in the full run.

## 7. Proposed final schema

**9 entity types** (one more than the target of about 8):

| Type | Definition | Key properties |
|---|---|---|
| **Service** | Something a citizen can apply for, receive or complete: benefits, programs, licences, registrations, loans, tests, courses, applications | `name`, `kind` (benefit · program · licence · loan · test · procedure) |
| **Organization** *(renamed from Agency)* | Agencies, offices, schools, servicers, dealers, or any organisation that provides, issues or decides | `name`, `kind` (agency · office · school · servicer · other) |
| **Document** | Forms, certificates, proofs, cards, letters, notices | `name`, `form_number` (optional) |
| **Requirement** | A condition or obligation: eligibility criteria, documents to present, restrictions | `name`, `text` (verbatim condition), `negated` (bool, e.g. "photocopies are not accepted") |
| **Amount** *(renamed from Fee)* | A monetary value or limit: fee, tax, premium, benefit amount, income or earnings limit | `name`, `value` (verbatim, e.g. "$25", "3.25%"), `kind` (fee · tax · premium · benefit · limit) |
| **TimeLimit** | A deadline, duration, frequency or waiting period | `name`, `value` (verbatim, e.g. "within 12 months", "every 12 months") |
| **Role** | A category of person the content applies to: applicant groups, statuses, relatives, officials | `name` |
| **Outcome** | A result or consequence of an action or condition (benefit reduced, licence suspended) | `name`, `text` |
| **ContactPoint** *(new)* | A phone number, website, online account, office location, or information page | `name`, `value` (number or URL text), `kind` (phone · website · account · office) |

**10 relation types**, each with a fixed direction:

| Relation | Domain → Range | Covers (pilot) |
|---|---|---:|
| REQUIRES | Service / Document / Role → Requirement / Document / Service | 63 |
| LEADS_TO | Service / Requirement / Outcome → Outcome / Service | 21 |
| DETERMINED_BY *(new)* | Amount / Service / Outcome → Requirement / Role / Amount | 20 |
| EXEMPT_FROM | Role / Service / Document → Requirement / Amount / Service | 18 |
| AVAILABLE_AT *(new)* | Service / Document → ContactPoint / Organization | 18 |
| APPLIES_TO | Service / Requirement / Amount / TimeLimit → Role / Service | 16 |
| PROVIDED_BY | Service / Document / Amount → Organization | 13 |
| PART_OF *(new)* | Service / Document / Amount → Service / Document / Amount | 13 |
| HAS_AMOUNT *(renamed from HAS_FEE)* | Service / Document → Amount | 7 |
| HAS_TIME_LIMIT *(renamed from HAS_DEADLINE)* | Service / Requirement / Document → TimeLimit | 9 |

This leaves out **ALTERNATIVE_TO** (3 mentions). Keeping both it and DETERMINED_BY gives 11 relations; see decision 2 below.

Pilot coverage of this schema, from the §5 mapping: **251 of 318 entities (78.9%)** and **201 of 264 relations (76.1%)**, counting inverse-direction mentions once they are flipped. Without ALTERNATIVE_TO, relation coverage is 198 (75.0%).

Every extracted node and relation keeps `evidence` (a verbatim quote) and `section_id`. In the metagraph, each normalised entity links back to the Section where it was mentioned.

**Changes to the extraction prompt for the full run:**
- Closed type lists with one-line definitions, plus explicit domain → range rules for each relation.
- `name` must be the surface noun phrase from the text, not CamelCase.
- `value` is mandatory for Amount, TimeLimit and ContactPoint.
- Requirement keeps the verbatim condition in `text`.
- No object-specific relation names and no self-loops.
- Evidence must be one contiguous quote with no "…".
- Sections longer than N characters, or table-like ones, get a per-section cap.

## 8. Decisions for review

1. **Rename Agency → Organization and Fee → Amount**, or keep the original names with broader definitions?
2. **Relations:** keep 10 (dropping ALTERNATIVE_TO), or allow 11? The recommendation is 11. ALTERNATIVE_TO is rare in the pilot but targets the "instead / or you can" dialogue pattern.
3. **Add ContactPoint as a 9th entity type?** The recommendation is yes, for "where / how do I contact" turns.
4. **Fee tables:** cap or skip table-like sections in the full run? The pilot shows they mostly produce row-level noise.
5. **Before the full run (4,114 sections),** re-run a pilot with the closed prompt on ~2 whole documents per domain? This would measure in-document entity overlap, which is needed to plan entity resolution.
