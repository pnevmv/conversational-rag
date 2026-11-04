# Human check of the LLM judge

Label each answer in `human_labels.csv` (column `label`: correct / partial / incorrect, or 1 / 0.5 / 0), with the same rules as the judge: correct = gives the key information of the reference (wording and length may differ, correct extra details are fine); partial = right topic but misses an important part or adds a wrong detail; incorrect = something else, misses the point, refuses although the information is available, or contradicts the document. If the reference is a clarifying question, a relevant clarifying question or correct information on that topic is correct. The history shows the last four turns, as the judge sees them.

## h001

**History**

```
Customer: I want to know more about the water issues at camp Lejeune
Agent: Did you serve at Marine Corps Base Camp Lejeune or Marine Corps Air Station MCAS New River in North Carolina ?
```

**Question.** no

**Reference.** Do you have qualifying service at Camp Lejeune and a current diagnosis of a qualifying condition?

**Answer.** If you didn’t serve at Marine Corps Base Camp Lejeune or Marine Corps Air Station MCAS New River in North Carolina, you may not qualify for Camp Lejeune water contamination-related disability benefits. If you’d like, tell me whether you lived at Camp Lejeune or MCAS New River with an active-duty Veteran who was your spouse or parent.

<details><summary>Gold section</summary>

Camp Lejeune Water Contamination Health Issues | Veterans Affairs#1 - Camp Lejeune water contamination health issues
Camp Lejeune water contamination health issues If you served at Marine Corps Base Camp Lejeune or Marine Corps Air Station MCAS New River in North Carolina , you may have had contact with contaminants in the drinking water there. Scientific and medical evidence has shown an association between exposure to these contaminants during military service and development of certain diseases later on. If you have qualifying service at Camp Lejeune and a current diagnosis of one of the conditions listed below , you may be able to get disability benefits.

</details>

## h002

**History**

```
Customer: Yes, I am.
Agent: First, thank you for your service. Because you served your country, you are protected under the Uniformed Service Employment and Reemployment Rights Act.
Customer: Is it okay if I ask another question? with regards to VA health insurance and benefits as a family member caring for a disabled veteran, am I eligible for benefits?
Agent: Yes, you apply to the request.
```

**Question.** Can my wife enjoy the benefits?

**Reference.** Yes, definitely.

**Answer.** You may qualify for health care benefits as a spouse, surviving spouse, dependent child, or family caregiver of a Veteran or service member. Find out if you qualify and how to apply, including applying online using VA Form 10-10EZ.

<details><summary>Gold section</summary>

VA.gov Home | Veterans Affairs#1 - Family member benefits
Family member benefits Learn about the benefits you may qualify for as a spouse, dependent, or survivor. And find out what you're eligible for as a family member caring for a Veteran with disabilities.

</details>

## h003

**History**

```
Customer: I did find out that I qualify for two different ones. How do I decide what to do now?
Agent: We can help you make the right decision for you to help maximize the benefits in your situation.
Customer: Ok thank you, and about accessing and managing the VA benefits and health care, what benefits can someone who is a service member find?
Agent: On our page you can find out what benefits you may be eligible for during service and which time-sensitive benefits to consider when separating or retiring.
```

**Question.** Could you give me some info about my qualifications for more than one VA education benefit? Is there any need for me to make a phone call? Deafness is a condition that I suffer from. Is there a phone number for people who are deaf or hard of hearing?

**Reference.** Yes, we have a regular phone number as well as a TTY phone number.

**Answer.** Yes, you may qualify for more than one VA education benefit, but you can’t receive benefits under more than one program at the same time. If you have hearing loss, call TTY 711 (or 888-GI-BILL-1 for the general line).

<details><summary>Gold section</summary>

Montgomery GI Bill Active Duty (MGIB-AD) | Veterans Affairs#1 - Can I qualify for more than one VA education benefit?
Can I qualify for more than one VA education benefit? Yes. You may qualify for more than one education benefit. If you re eligible for more than one , you ll need to decide which to receive. You can t receive benefits under more than one program at a time. We can help you make this decision. Call us at 888-GI - BILL-1 888 - 442 - 4551 , Monday through Friday , 8:00 a.m. to 7:00 p.m. ET. If you have hearing loss , call TTY : 711. GI Bill is a registered trademark of the United States Department of Veterans Affairs VA. The absence of the registration symbol does not constitute a waiver of VA s trademark rights in that phrase. Read our Terms of Use

</details>

## h004

**History**

```
Customer: I might not be able to pay my mortgage. What if I'm on the verge of becoming homeless? So, what happens next?
Agent: Please visit our website to learn about VA programs for Veterans who are homeless and learn about our homelessness programs. Contact the National Call Center for Homeless Veterans at 877-424-3838 for help 24 hours a day, 7 days a week.
Customer: Is there anything else I should know about the VA Medical Center? What do you suggest?
Agent: Find these and other resources near you
```

**Question.** Where can i get more information?

**Reference.** Learn about suicide prevention and the support we offer. Visit our suicide prevention website
   Visit our Make the Connection website for resources and to see stories of veterans who have overcome depression and other mental health challenges.

**Answer.** You can call our general VA hotline at 800-827-1000, Monday through Friday, 8:00 a.m. to 9:00 p.m. ET, or call your nearest VA medical center to learn more about your options. If you’re homeless or at risk of becoming homeless, you can also contact the National Call Center for Homeless Veterans at 877-424-3838 for free, confidential help 24/7.

<details><summary>Gold section</summary>

Veteran Suicide Prevention | Veterans Affairs#1 - You can also find information and support on our websites:
You can also find information and support on our websites: Get information about suicide prevention and the support we offer. Visit our suicide prevention website Go to our Make the Connection website to get resources and watch stories of Veterans who ve overcome depression and other mental health challenges. Visit Make the Connection

</details>

## h005

**History**

```
Customer: yes
Agent: Ok great! Thank you for your response. You can ask the city or county you are in about that
Customer: Is there anyway to become exempt from them?
Agent: You can contact the DMV Call Center
```

**Question.** Do you know where the centers are located?

**Reference.** yes I do. New York City Bronx, Kings (Brooklyn), New York (Manhattan), Queens, Richmond (Staten Island)

**Answer.** If you reside outside New York City and you’re exempt from the vehicle use tax in your county, you complete form UT-11C. If you reside in New York City and you’re exempt, you get form UT-11 from a local DMV office or a DMV Call Center.

<details><summary>Gold section</summary>

Commercial vehicle registration fees, vehicle use taxes and supplemental fees#3 - New York City Bronx, Kings (Brooklyn), New York (Manhattan), Queens, Richmond (Staten Island)
New York City Bronx, Kings (Brooklyn), New York (Manhattan), Queens, Richmond (Staten Island) All passenger vehicle original registrations and renewals Vehicle use tax - $80 for 2 years $40 / year Livery and for - hire vehicles in these registration classes - $400 for 1 year 3 Livery OML Bus (OMR) Taxi OMT Supplemental MCTD fee - $50 for two years $25 per year Note : The New York City Taxi and Limousine Commission regulates all " TC " vehicle plates. All registrants for " TC " vehicle plates must pay the vehicle use tax.

</details>

## h006

**History**

```
Customer: Hello, can you tell me what the FAFSA completion data consists of?
Agent: It is noteworthy that each past year they are different from the numbers.
Customer: Can you tell me more about it?
Agent: It can happen due to several factors, also including the possibility that your institution appears more than once in the data.
```

**Question.** Maybe an unrelated question now from FAFSA completion, are these tips good at any college?

**Reference.** You should go to the schools you are interested in to get additional information.

**Answer.** Yes, the Financial Aid Toolkit resources are meant for counselors and other college access professionals to help increase FAFSA completion. You should also check your state or college deadlines, since FAFSA deadlines affect whether you qualify for state or school aid.

<details><summary>Gold section</summary>

Understanding College Costs | Federal Student Aid#1 - How can I lower the cost of college?
How can I lower the cost of college? Here are some suggestions on how you might be able to lower the cost of college. For many of these suggestions , you ll want to follow up with the colleges or career schools you are interested in to get additional details. Set a budget and stick to it! Having a budget will help you compare anticipated college or career school expenses against your potential available income and financial aid. You also can use a budget to compare costs between different schools. Learn about budgeting. College or career school costs can vary significantly and there are many schools with affordable tuition and generous financial assistance. Make sure to research all schools that may meet your academic and financial needs. To find colleges or career schools , use our college search tool, College Navigator. You may be able to get school credit based on your knowledge or life experiences , and you can manage your course work to reduce costs. Ask your school whether it s possible to test out of any classes. If you don t take a class , you may not have to pay for the credits. Some colleges give credit for life experiences, thereby reducing the number of credits needed for graduation. Most schools charge a set price for a specific number of credits taken in a semester. If academically possible , take the maximum number of credits allowed. This strategy reduces the amount of time needed to graduate. Some schools offer combined degree programs or three - year programs that allow you to take all of the courses needed for graduation in three years, instead of four, thereby eliminating one year's educational expenses. Colleges and career schools may offer discounts on tuition if you are a child of an alumnus or alumna i.e., if your parent went to the school ; more than one family member is enrolled at the school ; you are a student government leader or the editor of the college newspaper or yearbook ; you are an older student ; your family s main wage earner is unemployed ; or you or a member of your family works at the school. Housing costs can add up. Here are some tips for reducing your housing costs : If you go to a college or career school near home , consider living with your parents or other family. If you live off - campus , consider sharing a house or apartment with multiple housemates to cut down the cost of rent, and carpool to save on gas and parking. Most colleges and universities sponsor resident advisor programs that offer reduced tuition or reduced room and board costs if you work in a residence hall. You may be eligible for health care benefits including the following : Most young adults can stay on their parents family plan until they turn 26, even if they are married or still living with their parents. If you have been uninsured because of a pre - existing condition , you may be eligible to join the Pre - Existing Condition Insurance Plan. If you are in a new insurance plan , insurance companies cannot charge you a deductible or copays for recommended or preventive services such as flu shots or other immunizations. You can work part - time to pay part of your costs. Be sure your work and school schedules don t conflict and that you have enough time for studying. Here are a couple of options : The Federal Work - Study Program provides an opportunity to earn money while going to school. Ask schools if they participate in the program. Cooperative education programs allow students to alternate between working full - time and studying full - time. Most schools have placement offices that help students find employment and personnel offices that hire students to work on campus. Taking small steps can add up. For example , you can lower the cost of textbooks if you buy used books or rent textbooks if you won t need the books once you finish the class. A credit card can help you build a credit history, if you use it wisely. But use it for emergencies only and don t spend more than you can afford to pay. If you decide to get a credit card , make sure you understand the terms.

</details>

## h007

**History**

```
Customer: I have another concern about Post-9/11 GI Bill benefits, when will the checks begin to arrive?
Agent: If your decision notice shows at least a 10% disability rating, you will get your first payment within 15 days of the notice.
Customer: Now, regarding benefits. How do I get benefits if I apply?
Agent: You must present supporting evidence such as a doctor's report or medical test results that show that your disability
```

**Question.** By the way, after you get a disability rating, what do you expect? Is it possible that the ranking would assist me in obtaining healthcare as well?

**Reference.** Yes, disability compensation may include other benefits like health care

**Answer.** Yes, after you receive a disability rating, it’s used to help determine your eligibility for other benefits, including VA health care. Your disability rating is also used to determine your disability compensation rate for monthly payments.

<details><summary>Gold section</summary>

What To Expect After You Get A Disability Rating | Veterans Affairs#1 - What to expect after you get a disability rating
What to expect after you get a disability rating If you got a decision notice from us that confirms your disability rating the rating that measures the severity of your disability , you may be able to get disability compensation or benefits. Find out what benefits you can get. Disability compensation may include financial compensation payments as well as other benefits like health care or job training. If you haven t gotten your decision notice : Check your status , or Contact your nearest VA regional benefit office , or Call us at 800 - 827 - 1000, or Contact us online

</details>

## h008

**History**

```
Customer: How much will my service member pay for dependent coverage?
Agent: [65] Nothing.s   [66] We provide dependent coverage at no cost until the child is 18 years old , or sometimes longer if the child meets one of the requirements listed below .
Customer: Thank you so much. Yet another question. Is it possible for me to retain my coverage for up to two years after I leave the military?
Agent: Of course yes. but you must meet two requirements
```

**Question.** You also know about this, I'm still in service, can I get SGLI?

**Reference.** You can get SGLI group life insurance while you are serving

**Answer.** You may be eligible for full-time SGLI if you’re an active-duty member (Army, Navy, Air Force, Marines, or Coast Guard), a commissioned member of NOAA or the USPHS, a cadet or midshipman at a U.S. military academy, a member of ROTC on authorized training and practice cruises, or a member of the Ready Reserve or National Guard scheduled for at least 12 inactive training periods per year, among other listed categories. If you meet the criteria, you’ll be automatically signed up.

<details><summary>Gold section</summary>

About VA Insurance Options And Eligibility | Veterans Affairs#1 - VA life insurance options
VA life insurance options Servicemembers Group Life Insurance SGLI Get group life insurance while you re serving. Family Servicemembers Group Life Insurance FSGLI Add coverage for your spouse and dependent children children who rely on you for financial support. Traumatic Injury Protection TSGLI Get short - term financial support to help you recover from a severe injury. Veterans Group Life Insurance VGLI Get group life insurance once you ve ended your service. Service - Disabled Veterans Insurance S - DVI If you re disabled because of an injury or illness caused or made worse by your active service , continue your life insurance beyond 2 years after you leave the military. Veterans Mortgage Life Insurance VMLI If you have a severe service - connected disability , get mortgage protection insurance for a home that s been adapted to meet your needs.

</details>

## h009

**History**

```
Customer: please show me information about VADIP
Agent: The VA Dental Insurance Program VADIP offers discounted private dental insurance for Veterans and family members who meet certain requirements .
Customer: and how they determine if I am eligible for benefits
Agent: You may be eligible for VADIP if either of the below descriptions are true for you
```

**Question.** To find out if I qualify for VA dental benefits, how do I find out which dental diseases or dental conditions qualify for the benefit? I have false teeth and some functional teeth

**Reference.** What VA dental care benefits do I qualify for?

**Answer.** You can find out what VA dental care benefits you may qualify for by clicking the statement that best describes you, which puts you into a benefits class and lists the dental care you may qualify for. The information provided doesn’t specify a list of dental diseases or conditions (like dentures or functional teeth) to match to benefits.

<details><summary>Gold section</summary>

VA Dental Care | Veterans Affairs#1 - What VA dental care benefits do I qualify for?
What VA dental care benefits do I qualify for? Click on the statement below that describes you best to find out your benefits class and the dental benefits you may qualify for : You re in : Class I You may qualify for: Any needed dental care You re in : Class IIC You may qualify for: Any needed dental care You re in: Class IV You may qualify for : Any needed dental care * *Please note: If you re being paid at the 100% disabling rate based on a temporary rating for a reason such as a long stay in the hospital or rehab care , that doesn t qualify you for this benefit. You re in: Class IV You may qualify for : Any needed dental care * *Please note: If you re being paid at the 100% disabling rate based on a temporary rating for a reason such as a long stay in the hospital or rehab care , that doesn t qualify you for this benefit. You re in: Class II You may qualify for: One - time dental care if you meet all of the requirements listed below All of these must be true for you : You didn t receive a dishonorable discharge , and You apply for dental care within 180 days of discharge or release , and Your DD214 certificate of discharge doesn t show that you had a complete dental exam and all needed dental treatment before you were discharged * Please note: If you got a dental award letter from VBA dated before 1955 stating that your dental conditions aren t compensable , then you are no longer eligible for Class II outpatient dental treatment. This is because of Public Law 83, which was enacted June 16 , 1955, and which amended Veterans eligibility for outpatient dental services. You re in : Class IIA You may qualify for: Any dental care needed to make sure you have and can keep a functioning dentition a working set of teeth You should know: A Dental Trauma Rating VA Form 10 - 564-D or VA Regional Office Rating Decision letter VA Form 10 - 7131 will tell you the tooth / teeth / condition that are trauma rated. You re in: Class III You may qualify for: Dental care to treat the oral conditions that a VA dental care provider concludes are directly making your service - connected health condition worse You re in: Class V You may qualify for: Dental care that a VA dental care provider concludes is needed to achieve at least one of the goals listed below The dental care must be needed to : Make it possible for you to be in the vocational rehab program , or Make it possible for you to reach the goals of your vocational rehab program , or Prevent you from having to stop your rehab program , or Help you get back to your rehab program faster if you ve had to stop and are in interrupted or leave status , or Help you get back to your rehab program faster if you ve had to stop and are in discontinued status because of an illness, injury, or dental condition , or Make it possible for you to get and adjust to a job during the period of employment assistance , or Make it possible for you to be fully independent in your daily living You re in: Class VI You may qualify for: Dental care to treat the dental issue that a VA dental care provider finds is making the health condition you re being treated for harder to treat You re in: Class IIB You may qualify for: A one - time course of dental care that a VA dental care provider concludes you need to achieve at least one of the goals listed below. The dental care must be needed to : Relieve your pain , or Help you get a job , or Treat your moderate, severe, or complicated and severe gingival and periodontal conditions gum infections that can lead to pain, swelling, and bone and tooth loss if not treated You re in: Inpatient status You may qualify for: Dental services that a VA dental care provider working with your primary care provider concludes you need to manage a health condition a doctor is currently treating you for

</details>

## h010

**History**

```
Customer: What schools are in the program?
Agent: Of note, you may be eligible for disbursement and other benefits.
Customer: What does that plan consist of, please?
Agent: That is, if you have a credit balance, it can be used for other things.
```

**Question.** What other charges can be implemented?

**Reference.** Schools must provide the information respectively.

**Answer.** If your loan is placed with a collection agency after you default, you may have to pay collection costs, including a private collection agency fee that’s usually 17.92% of your outstanding balance (principal, interest, and fees). You could also face other costs such as Treasury offset processing fees and costs related to possible civil litigation.

<details><summary>Gold section</summary>

Receiving Financial Aid | Federal Student Aid#1 - Paying for Textbooks and Other Course Materials If You Haven t Received Your Financial Aid
Paying for Textbooks and Other Course Materials If You Haven t Received Your Financial Aid Schools that participate in federal student aid programs must provide a way for you to obtain your books and supplies by the seventh day of the term if you are eligible for disbursement i.e., the payment of your financial aid 10 days before the term begins and you will have a credit balance i.e., money left over after your financial aid is applied to your tuition, fees, and other school charges as applicable. Your school can tell you if the above criteria apply to you.

</details>

## h011

**History**

```
Customer: What follows after passing the test?
Agent: You must first schedule and take a practical exam
Customer: If I wanted additional classes, how should I pay?
Agent: Do you want to pay for additional tests?
```

**Question.** No, I'm just asking at home that I want to pay later...

**Reference.** Ok, of course if you want you can pay for classes adi...

**Answer.** If you want to pay for additional road tests, you can pay online or by phone after you fail your road test. To pay, you must have a valid learner permit or driver license and provide your DMV ID Number, your Learner Permit Client ID Number, and your date of birth, then pay with a credit or debit card.

<details><summary>Gold section</summary>

Schedule and take a road test#1 - How to pay for additional tests
How to pay for additional tests If you fail your road test , you can pay for additional tests online or by phone. To pay , you must have a valid learner permit or driver license provide your DMV ID Number from your Learner Permit Client ID Number and your date of birth have no other road tests currently available pay the fee with a credit or debit card 7 Pay additional road test fees online [11 ] Pay additional fees by phone : 1 - 518 - 402 - 2100 For information about how to get a Pre - Licensing Course Certificate MV-278 , see Prepare for your road test [12]. The fee for up to two road tests for a non - commercial license is included in your $10.00 driver license application fee. Usually, the earliest date is within three to five weeks , but at peak testing periods during summer and school breaks it may be up to 10 weeks away. There are no waiting lists. If you have an interim or temporary learner permit without a photo , you must also show a NY State photo driver license or a NY State non - driver ID Card. Photo documents from other states are not acceptable. The vehicle must have functional seat belts, headlights, windshield wipers and other equipment, a front passenger area and seatbelt free of trash, clutter or debris that might stain or damage the license examiner s uniform, and a front passenger door that is able to be opened from the inside of the vehicle The motorcycle must not have more than three wheels in contact with the ground The DMV accepts : American Express Card Discover Card /Novus MasterCard MasterCard Debit card without personal identification number PIN VISA Card Visa Debit Card without personal identification number PIN

</details>

## h012

**History**

```
Customer: Is that rate stable or does it vary? . Who should I contact if my recovered vehicle was damaged or totaled?
Agent: You would need to contact your auto insurance company.
Customer: Just a random question. If my car is stolen, what do I do?
Agent: Your insurance company: 1) will issue you 2 original NY State Insurance ID cards with barcode (see sample) or provide you access to your NY State Insurance 2 digital electronic ID card) will send you an electronic notice of insurance coverage to DMV (your insurance agent or broker cannot present this notice) Your NY State Insurance ID cards and electronic notice together verify your coverage. We need both.
```

**Question.** What kind of proof of insurance do I need?

**Reference.** Your insurance company will issue proof of insurance in two ways: It will give you two original NY State Insurance ID Cards or provide you with access to your digital electronic NY State Insurance ID Card

**Answer.** You need auto liability insurance to register your vehicle in New York. Your insurance company will issue two original NY State Insurance ID Cards or provide access to a digital electronic NY State Insurance ID Card, and you must have both the ID cards and the electronic notice of insurance coverage from your insurance company.

<details><summary>Gold section</summary>

New York State Insurance Requirements#3 - Do I need insurance to register my vehicle?
Do I need insurance to register my vehicle? Yes. The DMV requires auto liability insurance to register a vehicle in New York. When you get insurance , your insurance company will issue proof of insurance in two ways. It will give you two original NY State Insurance ID Cards see a sample [3] or provide you with access to your digital electronic NY State Insurance ID Card 3 send an electronic notice of insurance coverage to the DMV your insurance agent or broker cannot file this notice Your NY State Insurance Identification Cards and the electronic notice of insurance together verify your insurance coverage. We need both. You must register your vehicle at the DMV within 180 days of the effective date on your insurance ID card. Bring one copy or form of your Insurance Identification Cards with you. The DMV office will keep the paper card. Keep the other paper card with the vehicle as your proof of insurance. Anyone operating your vehicle must be able to provide proof of insurance while they are operating the vehicle.

</details>

## h013

**History**

```
Customer: is this where I go to complain?
Agent: Your feedback is important to us. You can submit a complaint , give us positive feedback, or review an already submitted case.
Customer: what can I do next if I don't agree with what Federal Student Aid decided?
Agent: You can follow our procedures for resolving disputes.  We encourage you to do this before you contact the Federal Student Aid Ombudsman Group
```

**Question.** By the way, regarding PLUS loans from the Direct Loan Program, how much money can I borrow with a PLUS loan?

**Reference.** The most you can borrow with a PLUS loan is the cost of attendance at the school your child would attend minus any other financial assistance and the school determines what the cost of attending there is.

**Answer.** You can borrow up to the cost of attendance at your child’s school minus any other financial assistance your child receives.

<details><summary>Gold section</summary>

Parent PLUS Loans | Federal Student Aid#1 - How much can I borrow?
How much can I borrow? The maximum PLUS loan amount you can borrow is the cost of attendance at the school your child will attend minus any other financial assistance your child receives. The cost of attendance is determined by the school.

</details>

## h014

**History**

```
(this is the first turn)
```

**Question.** how do you only apply for medicare?

**Reference.** are you 65?

**Answer.** You can apply online for Medicare only even if you are not ready to retire, and it takes less than 10 minutes. Once you submit your electronic application, you’re usually done and you’ll receive your Medicare card in the mail.

<details><summary>Gold section</summary>

Benefits Planner: Retirement | Applying for Medicare Only | Social Security Administration#2 - Applying for Medicare Only
Applying for Medicare Only If you are within three months of age 65 or older and not ready to start your monthly Social Security benefits yet , you can use our online retirement application to sign up just for Medicare and wait to apply for your retirement or spouses benefits later. Before you decide , you need to be sure that you understand how waiting until later will affect : the lifetime benefits we can pay on your account and your health insurance coverage.

</details>

## h015

**History**

```
Customer: yes
Agent: you can receive a conditional driving privilege or a restricted driving privilege to drive in NY State . The conditions or the restrictions are the same as the conditions or restrictions for a driver with a NY State driver license
Customer: how is the conditional license?
Agent: The DMV can issue a conditional license to a qualified driver whose NY State license has been suspended or revoked because of an alcohol or drug - related violation
```

**Question.** and what documents do you require?

**Reference.** Proof of identity, such as a valid license, birth certificate, or passport, with your full name, middle name if applicable, and last name. This name,

**Answer.** You must provide proof of the driver license you have issued in another state and meet the other requirements to get a conditional driving privilege or restricted driving privilege. The conditions or restrictions you follow will be the same as those for a driver with a NY State driver license.

<details><summary>Gold section</summary>

Federal REAL ID#3 - You MUST bring to the office the following original or certified proof documents:
You MUST bring to the office the following original or certified proof documents: Proof of identity , such as valid license, birth certificate or passport, with your full first, middle if applicable and last name. This name , as it appears on your proof of identity , will be displayed on your card as required by federal law. Proof of Social Security Number or Social Security Number ineligibility. If you a valid NY license, permit or ID card , you must bring your original social security card or W-2 with full SSN. If you a New York State driver license or identification card , you must bring your Social Security Card or a letter from the Social Security Administration proving your ineligibility to have a social security number. If you lost your Social Security Card , you must get a duplicate before you come to the DMV. The Social Security Administration website has more information on obtaining a duplicate card [4]. Proof of your date of birth. Proof of U.S. citizenship , lawful permanent residency or temporary lawful status in the U.S. Two different proofs of New York State residence such as utility bill, bank statement or mortgage statement (P.O. Box not acceptable). This address will be displayed on your card. If the name on your license , permit , or non - driver ID application does not match the name on your identity, lawful status, and social security proofs you must bring in court or government issued proof documenting the event causing your name change such as a marriage license , divorce decree , adoption , or court order document. The application process also requires the DMV to take a new photo. Complete this guide to find out exactly what proof documents are needed before going to an office. Find your proofs [5 ]

</details>

## h016

**History**

```
Customer: yes
Agent: ou must bring an International Driving Permit or a certified translation of your driver license to the road test . The translation must be certified by a consulate , the US Department of State , or another official agency
Customer: but do I have to surrender my foreign license? What if I need my license when I return to my other country?
Agent: You can ask the road test examiner how to make sure that your foreign driver license is not destroyed
```

**Question.** something else I want to ask about students from other nations, residents will be consoled, I need more information

**Reference.** a judge considers these facts to decide if your intent is to make NY State a " fixed and permanent " residence. According to this law , students from other states or from other nations who attend school in New York State are usually not considered residents of NY State .

**Answer.** If you plan to return to your home country and will need your foreign driver license, you should ask the DMV road test examiner how to make sure it isn’t destroyed.

<details><summary>Gold section</summary>

Moving to NY#3 - If I have a driver license from another country and I have a NY State learner permit, can I drive without a supervising driver?
If I have a driver license from another country and I have a NY State learner permit, can I drive without a supervising driver? Yes. Your valid foreign driver license allows you to drive without a supervising driver. You can drive on any street, road, highway, bridge, or tunnel, except in a DMV road test area. If your driver license is printed in any language except English , you must bring an International Driving Permit or a certified translation of your driver license to the road test. The translation must be certified by a consulate, the US Department of State, or another official agency. The translation must include your name your date of birth the expiration date of your foreign driver license a list of the types of vehicles that your foreign driver license allows you to drive If you have a NY State learner permit, and you do not have a valid foreign driver license , NY State law requires a supervising driver to ride with you. The supervising driver must be age 21 or over and must have a valid driver license to operate the vehicle that you drive. Definition of Resident per Section 250 5 of the NY State Vehicle and Traffic Law : " As used in this section, the term' resident' shall mean domiciliary, that is, one who lives in this state with the intention of making it a fixed and permanent abode. It shall be presumptive evidence that a person who maintains a place of abode in this state for a period of at least ninety days is a resident of this state. " To live in a house, a home, an apartment, a room or other similar place in NY State for 90 days is considered " presumptive evidence " that you are a resident of New York State. A police officer can use this as evidence to issue a traffic ticket if you drive in New York State without a NY State driver license or vehicle registration. A judge considers the law and the evidence of your intent and decides if you are a resident of New York State. If you pay taxes or your children attend school in another state , a judge considers these facts to decide if your intent is to make NY State a " fixed and permanent " residence. According to this law , students from other states or from other nations who attend school in New York State are usually not considered residents of NY State. DMV does not decide if you are a resident of New York State, if you must get a NY State driver license, or if you must register your vehicle in New York State.

</details>

## h017

**History**

```
Customer: Can you tell me some of the organizations that are exempt from the search fees?
Agent: Some of the exempted organizations are any public organization, its officers, a volunteer fire company, volunteer ambulance service, etc. These organizations are exempt from the search fee.
Customer: What to do in case none of the users performed a search that the DMV contacted me for?
Agent: You should contact the DMV immediately.
```

**Question.** Why would the DMV contact me about a search?

**Reference.** The DMV may contact you to ask you about a search to make sure you comply with the Dial-In Terms of Service.

**Answer.** DMV may contact you about a DIAL-IN search you performed to monitor compliance with the DIAL-IN Terms of Service. You must respond with any business records that support your search, or your search privileges may be suspended until you respond.

<details><summary>Gold section</summary>

DIAL-IN search accounts#3 - Will DMV contact me about the searches I perform using my DIAL-IN Search Account?
Will DMV contact me about the searches I perform using my DIAL-IN Search Account? Yes , DMV may ask you about a DIAL - IN search you performed. We inquire about searches to monitor compliance with the DIAL - IN Terms of Service . You must respond to the inquiry whether or not you have business records that support your search. Your response will be considered an incomplete reply if you do not give us the business records. You can complete an inquiry at any time if you send us the requested acceptable business records. If you performed the search on behalf of a client , you will need to show permissible use of your client, and your client agent relationship. If you personally did not perform the search we have inquired about , please check with the other users of your DIAL - IN account to see if one of them performed the search. If none of the known users performed the search , contact us immediately. If you do not respond to our inquiry about a DIAL - IN search, your search privileges will be suspended until you respond.

</details>

## h018

**History**

```
Customer: how Exchange a NY State driver license for a non-driver ID card?
Agent: You can exchange a New York State driver license or learner permit that is current or that expired within the last 2 years for a New York State non - driver ID card NDID
```

**Question.** I need information from Proof of Supplemental Security Income

**Reference.** you receive SSI?

**Answer.** To prove you receive Supplemental Security Income (SSI) at the DMV, you must bring an original (not a photocopy) Notice of Award notifying you, COLA letter, SSA-L8151 Third Party Query letter, SSA-2258 Benefit Verification letter, or another listed SSI document. If you need the SSA-2258/benefit verification letter, call the Social Security Administration in advance at 1-800-772-1213.

<details><summary>Gold section</summary>

Exchange a NY State driver license for a non-driver ID card#1 - Proof of Supplemental Security Income (SSI)
Proof of Supplemental Security Income (SSI) To prove you receive SSI , you must bring one of the documents listed below to the DMV. The document must be the original, not photocopy. that you are eligible for SSI benefits Notice of Award notifying you Cost of Living Adjustment COLA letter Notice of change in payment SSA - L8151 Third Party Query TPQY letter Report of Confidential Social Security Information SSA-2258 Benefit Verification letter you must call the Social Security Administration in advance to obtain this letter : 1 - 800 - 772 - 1213 If you want to exchange in an office and keep your Standard document type , follow these steps : Step 1: Complete an Application for Permit , Driver License or Non - Driver ID Card PDF [4] MV-44 Step 2 : Come to an office. Bring your current license your application payment

</details>

## h019

**History**

```
Customer: What is an insurance lapse in New York State?
Agent: An insurance lapse means that there is no liability insurance coverage for a vehicle registered in New York State for a period of time
Agent: Do you have an insurance expiration for your registered vehicle?
```

**Question.** yes

**Reference.** the DMV can suspend your registration and driver license

**Answer.** An insurance lapse in New York State means there is no New York State auto liability insurance coverage for a period of time while your vehicle is registered. If your insurance coverage changes to a different name than what’s on your registration, it may cause a lapse and the DMV may suspend your driver license and vehicle registration.

<details><summary>Gold section</summary>

Insurance lapses#3 - What is an insurance lapse in New York State?
What is an insurance lapse in New York State? An insurance lapse means that there is no liability insurance coverage for a vehicle registered in New York State for a period of time. If there is a lapse of insurance for a vehicle registered to you , the DMV can suspend your registration and driver license.

</details>

## h020

**History**

```
Customer: Under the Graduated Repayment Plan, how are monthly payments for consolidation loans handled?
Agent: null
Customer: can I ask something else? Regarding the Perkins loan repayment plan? could it be consolidated? how can i pay it?
Agent: Check with your school for more information.
```

**Question.** ok good, regarding the simulation of borrowing more money, does the school determine the amount to lend that i need?

**Reference.** Yes, and here you can see how choice of school affects how much you may need to borrow.

**Answer.** You can find out what happens when you borrow more money through the Loan Simulator. The context does not say whether your school determines the amount to lend you.

<details><summary>Gold section</summary>

Loan Simulator | Federal Student Aid#1 - I Want to Simulate Borrowing More Money
I Want to Simulate Borrowing More Money Find out what happens when you borrow more money to pay for educational expenses, returning to school, or finishing your studies later than expected. Coming Soon Or Start From Scratch Explore impacts when you borrow more. Find out about federal loan limits. See how choice of school affects how much you may need to borrow.

</details>

## h021

**History**

```
Customer: I would rather do a work that corresponds to my actual collection of skills. Could you assist me in this matter?
Agent: Surely, we can. You would have to go for a little process and find out if you can get employment counseling and job-search support.
Customer: Well, that's good to know that i have options available. Sorry about being repetitive, but you told me earlier that self employment was possible and that's not only for veterans, did you?
Agent: Totally correct. Not only veterans can apply for this, but service-members can too.
```

**Question.** Well, that's good to know that i have options available. Sorry about being repetitive, but you told me earlier that self employment was possible and that's not only for veterans, did you?

**Reference.** Totally correct. Not only veterans can apply for this, but service-members can too.

**Answer.** If you’re a service member or Veteran with a service-connected disability and an employment barrier, you may be able to get help through the VR&E Self-Employment track to start your own business. You can get employment counseling and job-search support through other VR&E tracks if you prefer work that matches your skills.

<details><summary>Gold section</summary>

Veterans Vocational Rehabilitation Programs | Veterans Affairs#1 - Veterans Vocational Rehabilitation programs
Veterans Vocational Rehabilitation programs If you re a Veteran or service member with a service - connected disability that impacts your ability to work , the Vocational Rehabilitation and Employment program also called Voc Rehab, VR&E, or Chapter 31 benefits may be able to help. We offer 5 support - and - services tracks to help you find and keep a job, and live as independently as possible. Explore the different tracks and find out how to apply for benefits and services. Reemployment trackYou may have the right to return to the civilian job you held before you deployed. Find out how we can help with this process. Rapid Access to Employment trackIf you want a job that matches your existing skills, find out if you can get employment counseling and job - search support. Self - Employment trackIf you re a service member or Veteran with a service - connected disability , find out how we can help you start your own business. Employment through Long - Term Services trackFind out if you may be eligible for vocational training to help you develop new job skills. Independent Living trackLearn about services that can help you live as independently as possible if you can't return to work right away.

</details>

## h022

**History**

```
Customer: Although, in that regard, what can i use to get more information? Something like this?
Agent: You can use our toll free number at 1-800-772-1213. There you'll have total confidentiality.
Customer: I have one more question regarding benefit claim, what happens if my spouse is already earning benefits?
Agent: If you spouse and you apply at the same time or spouse is receiving benefits all ready, then we will automatically check your eligibility for benefits as a spouse.
```

**Question.** In the event that my divorced spouse or ex-spouse dies, can I receive any survivor benefits from you?

**Reference.** In fact, you can. If that scenario happens, you may be eligible for a higher survivor benefit based on her work. In case the deceased person is your ex-spouse, you may be eligible for a higher benefit even of you are already receiving a survivor benefit on another spouse.

**Answer.** Yes, if you are the divorced spouse of a worker who dies, you could get survivor benefits the same as a widow or widower if your marriage lasted 10 years or more. If your ex-spouse dies, you may also be eligible for a higher survivor benefit based on his or her work, even if you are already receiving a survivor benefit on another spouse.

<details><summary>Gold section</summary>

Explore The Benefits You May Be Due#1 - You, or Your Family Members, May Be Eligible for Increased Benefits
You, or Your Family Members, May Be Eligible for Increased Benefits Our mission is to deliver Social Security services that meet the changing needs of the public. It's not unusual for a benefit recipient's circumstances to change after they apply or became eligible for benefits. If you, or a family member, receive Social Security or Supplemental Security Income SSI , certain life changes may affect eligibility for an increase in your federal benefits. For example , if your spouse or ex - spouse dies , you may become eligible for a higher Social Security benefit. To find out if you, or a family member, might be eligible for a benefit based on another person s work, or a higher benefit based on your own work , see the information about benefits on the Social Security website. You can also use the Benefit Eligibility Screening Tool BEST to find out if you could get benefits that Social Security administers. Based on your answers to questions , this tool will list benefits for which you might be eligible and tell you more information about how to qualify and apply. The questions and answers below are about a few of the life changes that could possibly increase your benefits. If your spouse or ex - spouse has died , you may be eligible for a higher survivor benefit based on his or her work. The death of an ex - spouse may allow you to be eligible for a higher survivor benefit even if you are already receiving a survivor benefit on another spouse. If you are at least age 65 , you may be eligible for cash benefits on your own record. If you are full retirement age or older , you can work and receive your monthly Social Security benefits, no matter how much you earn. Please review this publication for more information. If your child had enough work credits and was providing at least half of your support , you may be eligible for a higher parent's benefit based on his or her work. If you have worked , you may be eligible for a higher retirement benefit based on your own work. If you have worked , you may be eligible for a higher disability benefit based on your own work. If you are at least 62 years old and unmarried , you may be eligible for a benefit based on a former spouse s work if that marriage lasted 10 years or more. You may be eligible for spouse's benefits if you have in your care a child who is under age 16 or disabled prior to age 22. Your child may be eligible for benefits based on your work. If you served in the U.S. military , you may be eligible for benefits through the Veterans Administration. Visit this link for more information: http://www.va.gov/ If you are unmarried and under age 18 or were disabled prior to age 22, and your parent is deceased or receiving Social Security benefits , you may be eligible for child benefits based on your parent s work. You may be able to get additional income through the Supplemental Security Income program, which helps seniors and the disabled who have limited income and financial resources. IMPORTANT : If you are receiving benefits , there are certain life events that you are required to report. For a complete list , please select the publication below that applies to the type of benefits you receive. NOTE : Failure to report a change may result in an overpayment. What You Need To Know When You Get Retirement Or Survivors Benefits 7 - 13 What You Need To Know When You Get Social Security Disability Benefits 11 - 18 What You Need To Know When You Get Supplemental Security Income SSI 7 - 19

</details>

## h023

**History**

```
Customer: Could I be eligible for the military service deferment?
Agent: Are you on active duty military service in connection with a war, military operation, or national emergency?
Customer: yes, I am in military service.
Agent: Then you could be eligible for the military service deferment.
```

**Question.** Am I making progress toward forgiveness when on an deferment?

**Reference.** On a deferment you have no payment, but it will not allow you to make progress toward forgiveness.

**Answer.** No, if you’re on deferment you probably won’t be making progress toward forgiveness, and you also won’t be making progress toward paying back your loan. If you’re pursuing PSLF or income-driven repayment forgiveness, deferment in most cases won’t count toward your forgiveness requirements.

<details><summary>Gold section</summary>

Student Loan Deferment | Federal Student Aid#1 - Get Relief With Lower Payments on an Income-Driven Repayment Plan
Get Relief With Lower Payments on an Income-Driven Repayment Plan If you re having trouble repaying your loans due to circumstances that may continue for an extended period, or if you re unsure when you ll be able to afford to make your monthly loan payments again , a better option might be to consider changing to an income - driven repayment plan. Income - driven repayment plans base your monthly payments on your income and family size. In some cases , your payment could be as low as $0 per month. Income - driven plans can also provide loan forgiveness if your loan isn t paid in full after 20 or 25 years. Always contact your student loan servicer immediately if you re having trouble making your student loan payments. If you re seeking Public Service Loan Forgiveness PSLF or income - driven repayment forgiveness , in most cases deferment will not allow you to make progress toward forgiveness.

</details>

## h024

**History**

```
Customer: but can you start with the resources about what insurance I need?
Agent: Would you like to know more about how much life insurance you need?
Customer: yes I would so I don't overpay
Agent: You can use the life insurance needs calculator and VGLI comparison questionnaire to help you decide how much life insurance you need
```

**Question.** I have another question about Accessing and Managing Your VA Benefits and Care. What can I check about the benefits

**Reference.** You will be ablel to check your Post-9/11 GI Bill benefits; view payment history; or change your current education benefits.

**Answer.** You can check the status of a disability or pension claim online, and you can also refill your prescriptions and send a secure message to your VA health care provider through VA.gov.

<details><summary>Gold section</summary>

VA.gov Home | Veterans Affairs#1 - Education
Education Check your Post-9/11 GI Bill benefits View your payment history Change your current education benefits Compare GI Bill benefits by school Apply for education benefits

</details>

## h025

**History**

```
Customer: I'm here to look at a good repayment plan
Agent: Are you looking for a repayment plan with affordable payments?
Customer: no looking for information on any plan affordable or not
Agent: Unfortunately, no relevant information is found.
```

**Question.** who can I talk to so I can get some options?

**Reference.** You can contact your loan servicer if you would like to discuss repayment plan options.

**Answer.** You can talk to your loan servicer to discuss repayment plan options or change your repayment plan. Before you contact them, you can also use the Loan Simulator to see which plans you may be eligible for and estimate your monthly payments.

<details><summary>Gold section</summary>

Repayment Plans | Federal Student Aid#1 - Choose the federal student loan repayment plan that s best for you.
Choose the federal student loan repayment plan that s best for you. To make your payments more affordable , repayment plans can give you more time to repay your loans or can be based on your income. Although you may select or be assigned a repayment plan when you first begin repaying your student loan , you can change repayment plans at any time for free. Contact your loan servicer if you would like to discuss repayment plan options or change your repayment plan. You can get information about all of the federal student loans you have received and find the loan servicer for your loans by logging in to " My Federal Student Aid. "

</details>

## h026

**History**

```
Customer: what if i moved?
Agent: first change your address, then order a replacement
Customer: I'd like to ask another question regarding the fee chart. Do you have any resources that I can use to view the fees that I need to pay?
Agent: Yes, I can link you to a table that shows the fees
```

**Question.** what's the cost for a motorcycle license?

**Reference.** The fees you pay when you get your first motorcycle license will depend on whether or not you currently have another class of New York State driver license and your exact age when you apply.

**Answer.** For a Class M or MJ motorcycle license (or to add class M or MJ), the fees range from $21 to $120 depending on whether you already have another New York State driver license and your age when you apply, and we can’t calculate your exact fee until you apply.

<details><summary>Gold section</summary>

Driver license and learner permit fees and refunds#3 - Fee for a motorcycle license
Fee for a motorcycle license The fees you pay when you get your first motorcycle license depend on whether or not you currently have another class of New York State driver license and your exact age when you apply. The fees for a Class M or MJ driver license, or to add class M or MJ to your current driver license, can range from $21 to $120. We cannot calculate your exact fee until you apply.

</details>

## h027

**History**

```
Customer: No, I on;t think I fit into this category
Agent: Unfortunately, no relevant information is found.
Customer: Is there a way for me to apply for a Direct Consolidation Loan if I want to have my borrower defense discharge apply to my FFEL?
Agent: You can apply by logging on to StudentAid.gov/app/launchConsolidation.action. Once your Direct Consolidation Loan is approved, you can then contact the borrower defense hotline on 1-855-279-6207 from 8am to 8pm
```

**Question.** What are the Discharge Criteria that I must follow if I want to be eligible for a 100% discharge of my Federal Program loans?

**Reference.** Were you enrolled when your school closed?

**Answer.** You may be eligible for a 100% discharge of your William D. Ford Federal Direct Loan Program loans, FFEL Program loans, or Federal Perkins Loans if you couldn’t complete your program because your school closed, and you were enrolled when it closed, on an approved leave of absence, or your school closed within 120 days after you withdrew. You are not eligible if you withdrew more than 120 days before the school closed (except in exceptional circumstances), you completed a comparable teach-out/transfer to another school, or you finished all coursework before the school closed even if you didn’t get a diploma or certificate.

<details><summary>Gold section</summary>

Closed School Discharge | Federal Student Aid#1 - Discharge Criteria
Discharge Criteria You may be eligible for a 100 percent discharge of your William D. Ford Federal Direct Loan Direct Loan Program loans, Federal Family Education Loan FFEL Program loans, or Federal Perkins Loans if you were unable to complete your program because your school closed, and if you were enrolled when your school closed ; you were on an approved leave of absence when your school closed ; or your school closed within 120 days after you withdrew. You are not eligible for discharge of your loans if your school closes and any of the following is true : Except in exceptional circumstances , you withdrew more than 120 days before the school closed. You are completing a comparable educational program at another school through a teach-out, by transferring academic credits or hours earned at the closed school to another school , or by any other comparable means. You completed all the coursework for the program before the school closed, even if you did not receive a diploma or certificate.

</details>

## h028

**History**

```
Customer: Of course, and regarding doing other types of work, to obtain the status of disabled I should not be able to do any type of work?
Agent: Yes, if you are unable to do any other type of work then you will be able to get disability.
Customer: I want to make sure that my family is taken care of financially after I pass away. What is the procedure for receiving Social Security survivor benefits?
Agent: Your Social Security can help ensure that your family is taken care of if you have earned enough credits through working.
```

**Question.** Thank you. I'd also like to know if the increase retroactive to January of the year you received money. What method is used to measure it?

**Reference.** we will recalculate your benefit amount

**Answer.** When you work and receive Social Security retirement or survivors benefits, your records are reviewed each year and your benefit is recalculated if your prior year earnings are higher than the years used to compute your benefit. If your benefit increases, Social Security pays the increase retroactive to January of the year after you earned the money.

<details><summary>Gold section</summary>

Benefits Planner: Retirement | Getting Benefits While Working | Social Security Administration#2 - Getting Benefits While Working
Getting Benefits While Working You can work while you receive Social Security retirement or survivors benefits. When you do , it could mean a higher benefit for you in the future. Each year we review the records for all working Social Security recipients. If your earnings for the prior year are higher than one of the years we used to compute your retirement benefit , we will recalculate your benefit amount. We pay the increase retroactive to January the year after you earned the money. Higher benefits can be important to you later in life and increase the future benefit amounts your family and your survivors could receive.

</details>

## h029

**History**

```
Customer: One more thing for Pay suspension termination fee. How do I know the status of my license or driving privilege after paying the fee?
Agent: Have you paid the fee online?
Customer: I have not yet.
Agent: How will I know the status of my license when I do pay the fee?
```

**Question.** You can sign up for a MyDMV account and use the My License service.

**Reference.** When will I get my license back?

**Answer.** After you pay the suspension termination fee, you can sign up for a MyDMV account and use the My License service to check the status of your driver license or driving privilege. If you need proof that the suspension was removed, you can order a certified copy of your driving record.

<details><summary>Gold section</summary>

Pay suspension termination fee#1 - When will I get my license back?
When will I get my license back? A definite suspension lasts until your suspension period ends. If you pay the suspension termination fee before the suspension period has ended , we will mail your license to you within 3 business days after the suspension period ends. 6 We will not mail your license to you if your driver license has expired you have a commercial driver license CDL 7 you have a conditional or restricted license 8 you have other suspensions, revocations or problems with your driver license

</details>

## h030

**History**

```
Customer: hello If my license is suspended for an insurance period, what can I do?
Agent: Your registration has not expired?
Customer: Yes
Agent: If your registration has not expired, you must turn in your plates. A driver's license is suspended when the lapse is 91 days or more or if the lapse time period has not yet been determined.
```

**Question.** Can someone else register the vehicle?

**Reference.** The DMV will not issue a record to any person unless that person makes an affidavit on Form FS-2. The statement certifies that the purpose of the application is not to avoid the results of the current suspension. The local DMV office determines if the request will be accepted or rejected.

**Answer.** No. If your registration is suspended for a lapse of insurance, the DMV will not issue a new registration to anyone to avoid that suspension, and it won’t issue one if the applicant has the same last name or lives at the same address as the registrant whose registration is suspended.

<details><summary>Gold section</summary>

Insurance lapses#3 - If my registration is suspended for a lapse of insurance, can another person register the vehicle?
If my registration is suspended for a lapse of insurance, can another person register the vehicle? No. The DMV will not issue a new registration if the DMV determines that the purpose of the new registration is to avoid the suspension. The DMV will not issue a registration if the applicant for the new registration has the same last name as the registrant whose registration is suspended , or resides at the same address as the registrant whose registration is suspended The DMV will not issue a registration to any person unless that person makes a sworn statement on form FS-2. The statement certifies that the purpose of the application in not to avoid the results from the current suspension. The local DMV Office determines if the application will be accepted or rejected. Form FS-2 is available only at a local DMV Office.

</details>

## h031

**History**

```
Customer: How do I choose the Direct Loan Master Promissory Note I want to preview?
Agent: Are you an Undergraduate Student?
```

**Question.** No, I am not an undergraduate student.

**Reference.** Are you a Gradudate Student?

**Answer.** Choose the Direct Loan MPN you want to preview or complete, and if you’re a graduate or professional student, use the MPN for Graduate/Professional Students. This MPN is a legal document in which you promise to repay your loan and any accrued interest and fees to the U.S. Department of Education.

<details><summary>Gold section</summary>

Completing a Master Promissory Note | Federal Student Aid#1 - I'm a Graduate/Professional Student
I'm a Graduate/Professional Student Find and use the MPN that you need as a graduate or professional degree student to borrow federal student loans. Graduate / professional students can be eligible for Direct Unsubsidized Loans, Direct PLUS Loans, or both. You need to complete an MPN for each loan type you intend to receive. You should request Direct Unsubsidized Loans up to your full eligibility before borrowing Direct PLUS Loans. Learn More Log In to Select MPN Type

</details>

## h032

**History**

```
Customer: Yes, I am.
Agent: First, thank you for your service. Because you served your country, you are protected under the Uniformed Service Employment and Reemployment Rights Act.
Customer: Is it okay if I ask another question? with regards to VA health insurance and benefits as a family member caring for a disabled veteran, am I eligible for benefits?
Agent: Yes, you apply to the request.
```

**Question.** Can my wife enjoy the benefits?

**Reference.** Yes, definitely.

**Answer.** Yes, if your wife is your spouse (or surviving spouse) she may qualify for VA health care benefits as a family member caring for a Veteran with disabilities. You can find out if you qualify and how to apply.

<details><summary>Gold section</summary>

VA.gov Home | Veterans Affairs#1 - Family member benefits
Family member benefits Learn about the benefits you may qualify for as a spouse, dependent, or survivor. And find out what you're eligible for as a family member caring for a Veteran with disabilities.

</details>

## h033

**History**

```
Customer: What are employment benefits for dependent family members?
Agent: Find out if you re eligible and how to apply to get career and educational counseling through VR&E as the dependent family member of a service member or Veteran with a service - connected disability .
Customer: Can I get Educational and Career Counseling services provided by VR&E (also called Chapter 36)?
Agent: You may be eligible for Educational and Career Counseling if you meet both of the requirements
```

**Question.** I'd also like to learn more about the VA MISSION Act. Are there any care requirements under the VA Mission Act?

**Reference.** Yes there are requirements

**Answer.** Under the VA MISSION Act, there are new eligibility criteria for community care. If you’re enrolled in VA health care, you can also find out how you may be able to receive care from a provider in your local community through community care.

<details><summary>Gold section</summary>

VA.gov Home | Veterans Affairs#1 - VA MISSION Act
VA MISSION Act Learn about new eligibility criteria for community care under the VA MISSION Act.

</details>

## h034

**History**

```
Customer: and what documents should i bring to the office?
Agent: Proof of identity, such as a valid license, birth certificate, or passport, with your full name, middle name if applicable, and last name.
Customer: Okay, that's it. There is something I'd like to know. Is it possible to get a conditional license?
Agent: The DMV can issue a conditional license to a qualified driver whose NY State license has been suspended or revoked because of an alcohol or drug - related violation . The driver must attend a Impaired Driver Program IDP previously known as Drinking Driving Program DDP approved by the DMV
```

**Question.** can a restricted use license be issued?

**Reference.** The DMV can issue a restricted use license to a driver who qualifies and whose license is suspended or revoked because of violations or incidents that are not alcohol or drug - related , or because of some drug - related violations

**Answer.** Yes, the DMV can issue a restricted use license to a driver who qualifies and whose license is suspended or revoked because of violations or incidents that are not alcohol or drug-related, or because of some drug-related violations. You must apply for a conditional or restricted use license in person at a DMV office.

<details><summary>Gold section</summary>

Conditional and restricted use licenses#3 - Restricted use
Restricted use The DMV can issue a restricted use license to a driver who qualifies and whose license is suspended or revoked because of violations or incidents that are not alcohol or drug - related, or because of some drug - related violations.

</details>

## h035

**History**

```
Agent: Yes, it will increase your future benefits.
Agent: Will your earnings be higher than one of the previous years?
Customer: Yes, they will be higher than the previous years earnings.
Agent: We will recalculate your benefit amount and pay the increase retroactive to January the year after you earned the money.
```

**Question.** How much can I earn and still get benefits?

**Reference.** If you are younger than full retirement age and make more than the yearly earning limit your benefits may reduce.

**Answer.** If you are under full retirement age and make more than the yearly earnings limit, your benefits may be reduced. For 2019, the limit is $17,640, and if you’re under full retirement age for the entire year, we deduct $1 from your benefits for every $2 you earn above that limit.

<details><summary>Gold section</summary>

Benefits Planner: Retirement | Getting Benefits While Working | Social Security Administration#2 - How Much Can I Earn And Still Get Benefits?
How Much Can I Earn And Still Get Benefits? If you are younger than full retirement age and make more than the yearly earnings limit , your earnings may reduce your benefit amount. (Full retirement age is 66 for people born between 1943 and 1954. Beginning with 1955, two months are added for every birth year until the full retirement age reaches 67 for people born in 1960 or later.) If you are under full retirement age for the entire year , we deduct $1 from your benefit payments for every $2 you earn above the annual limit. For 2019 , that limit is $17,640.

</details>

## h036

**History**

```
Agent: Yes. Your valid foreign driver's license allows you to drive without a supervising driver. You can drive on any street, highway, highway, bridge or tunnel, except in a DMV road test area.
Agent: What if my driver's license is printed in another language?
Customer: Yes
Agent: You must present an International Driving Permit or a certified translation of your driver's license to the test drive. The translation must be certified by a consulate, the United States Department of State or another official agency
```

**Question.** Very well. NOw for an International Driving Permit  . If I pass the exam

**Reference.** the examiner will give you an interim license that allows you to drive. Keep the interim license with your photo learner permit until your new license arrives in the mail in about 2 weeks

**Answer.** If you have a valid driver license from another country, you can drive in New York State without applying for a New York State driver license unless you become a New York State resident. You don’t need an International Driving Permit, but it is helpful because it verifies your license in several languages.

<details><summary>Gold section</summary>

Get a driver license#1 - Step 4: Pass a road test
Step 4: Pass a road test If you pass your test , the examiner will give you an interim license that allows you to drive. Keep the interim license with your photo learner permit until your new license arrives in the mail in about 2 weeks. See how to schedule and take a road test [8].

</details>

## h037

**History**

```
Customer: What requirements do I need?
Agent: Are you enrolled in VA Health Care?
Customer: do not
Agent: does not qualify as it does not meet all the requirements
```

**Question.** where to get more information about priority groups?

**Reference.** you can browse our website

**Answer.** You can find out more about VA health care priority groups and how they work under the “Priority groups” section. If you want, you can also call the VA general hotline at 800-827-1000 to ask about your care options.

<details><summary>Gold section</summary>

About VA Health Benefits | Veterans Affairs#1 - What care and services does VA health care cover?
What care and services does VA health care cover? Each Veteran s medical benefits package is unique. Yours will include care and services to help : Treat illnesses and injuries Prevent future health problems Improve your ability to function Enhance your quality of life All Veterans receive coverage for most care and services , but only some will qualify for added benefits like dental care. The full list of your covered benefits depends on : Your priority group , and The advice of your VA primary care provider your main doctor, nurse practitioner, or physician s assistant , and The medical standards for treating any health conditions you may have Learn more about priority groups You should also know that being signed up for VA health care meets your Affordable Care Act ACA health coverage requirement of having minimum essential health coverage. We ll update this site if the ACA changes with new laws. Learn more about the ACA, VA, and you

</details>

## h038

**History**

```
Customer: One more thing for Pay suspension termination fee. How do I know the status of my license or driving privilege after paying the fee?
Agent: Have you paid the fee online?
Customer: I have not yet.
Agent: How will I know the status of my license when I do pay the fee?
```

**Question.** You can sign up for a MyDMV account and use the My License service.

**Reference.** When will I get my license back?

**Answer.** After you pay the suspension termination fee, you can sign up for a MyDMV account and use the My License service to check the status of your driver license or driving privilege. If you need proof that DMV removed your suspension, you can order a certified copy of your driving record.

<details><summary>Gold section</summary>

Pay suspension termination fee#1 - When will I get my license back?
When will I get my license back? A definite suspension lasts until your suspension period ends. If you pay the suspension termination fee before the suspension period has ended , we will mail your license to you within 3 business days after the suspension period ends. 6 We will not mail your license to you if your driver license has expired you have a commercial driver license CDL 7 you have a conditional or restricted license 8 you have other suspensions, revocations or problems with your driver license

</details>

## h039

**History**

```
Customer: No I am not.
Agent: Are you a veteran with a service-connected disability?
Customer: No, I am not, I am a spouse to a veteran.
Agent: Unfortunately, no relevant information is found.
```

**Question.** Will I be allowed to return to a former job through VR&E?

**Reference.** Yes, you may be eligible for help if you're a veteran with a service-connected disability and you meet all of the requirements listed below.

**Answer.** You may be eligible for help through VR&E to return to your former job if you’re a Veteran with a service-connected disability and you would like to return to your former job, and you are enrolled in Vocational Rehabilitation and Employment VR&E.

<details><summary>Gold section</summary>

VR&E Reemployment Track | Veterans Affairs#1 - Can I get help returning to my former job through VR&E?
Can I get help returning to my former job through VR&E? You may be eligible for help if you re a Veteran with a service - connected disability , and you meet all of the requirements listed below. All of these must be true. You: Have an employment barrier or handicap , and Are enrolled in Vocational Rehabilitation and Employment VR&E , and Would like to return to your former job Note: Having an employment handicap means your service - connected disability limits your ability to prepare for, obtain, and maintain suitable employment a job that doesn t make your disability worse, is stable, and matches your abilities, aptitudes, and interests.

</details>

## h040

**History**

```
(this is the first turn)
```

**Question.** is this where I go to complain?

**Reference.** Your feedback is important to us. You can submit a complaint , give us positive feedback, or review an already submitted case.

**Answer.** If you have a complaint against a DMV-regulated repair shop or inspection-related business, you can contact the DMV Consumer & Facilities Services Complaint Unit. Their phone number is 1-518-474-8943 and their fax number is 1-518-486-4102.

<details><summary>Gold section</summary>

Feedback Center#1 - Feedback Center
Feedback Center Your feedback is important to us. You can submit a complaint an issue, concern, suspicious activity, or scam, give us positive feedback, or review an already submitted case. If you previously submitted a complaint and Federal Student Aid gave you a response you don't agree with , or you believe is incorrect , follow our procedure for resolving disputes. We encourage you to do this before you contact the Federal Student Aid Ombudsman Group. The Ombudsman Group is a neutral, informal, and confidential resource to help resolve disputes about your federal student aid.

</details>

## h041

**History**

```
Customer: No
Agent: Unfortunately, no relevant information is found.
Customer: How can I find out information on requirments for increase benefits?
Agent: It is important that you may be able to get additional income through supplemental income with certain life events
```

**Question.** What about eligibility based on my own work?

**Reference.** You may be eligible for a higher disability benefit based on your own work

**Answer.** If you have worked, you may be eligible for a higher retirement benefit based on your own work, and you may be eligible for a higher disability benefit based on your own work. You can also use the Benefit Eligibility Screening Tool (BEST) to find out which benefits you might qualify for and how to apply.

<details><summary>Gold section</summary>

Explore The Benefits You May Be Due#2 - You, or Your Family Members, May Be Eligible for Increased Benefits
You, or Your Family Members, May Be Eligible for Increased Benefits Our mission is to deliver Social Security services that meet the changing needs of the public. It's not unusual for a benefit recipient's circumstances to change after they apply or became eligible for benefits. If you, or a family member, receive Social Security or Supplemental Security Income SSI , certain life changes may affect eligibility for an increase in your federal benefits. For example , if your spouse or ex - spouse dies , you may become eligible for a higher Social Security benefit. To find out if you, or a family member, might be eligible for a benefit based on another person s work, or a higher benefit based on your own work , see the information about benefits on the Social Security website. You can also use the Benefit Eligibility Screening Tool BEST to find out if you could get benefits that Social Security administers. Based on your answers to questions , this tool will list benefits for which you might be eligible and tell you more information about how to qualify and apply. The questions and answers below are about a few of the life changes that could possibly increase your benefits. If your spouse or ex - spouse has died , you may be eligible for a higher survivor benefit based on his or her work. The death of an ex - spouse may allow you to be eligible for a higher survivor benefit even if you are already receiving a survivor benefit on another spouse. If you are at least age 65 , you may be eligible for cash benefits on your own record. If you are full retirement age or older , you can work and receive your monthly Social Security benefits, no matter how much you earn. Please review this publication for more information. If your child had enough work credits and was providing at least half of your support , you may be eligible for a higher parent's benefit based on his or her work. If you have worked , you may be eligible for a higher retirement benefit based on your own work. If you have worked , you may be eligible for a higher disability benefit based on your own work. If you are at least 62 years old and unmarried , you may be eligible for a benefit based on a former spouse s work if that marriage lasted 10 years or more. You may be eligible for spouse's benefits if you have in your care a child who is under age 16 or disabled prior to age 22. Your child may be eligible for benefits based on your work. If you served in the U.S. military , you may be eligible for benefits through the Veterans Administration. Visit this link for more information: http://www.va.gov/ If you are unmarried and under age 18 or were disabled prior to age 22, and your parent is deceased or receiving Social Security benefits , you may be eligible for child benefits based on your parent s work. You may be able to get additional income through the Supplemental Security Income program, which helps seniors and the disabled who have limited income and financial resources. IMPORTANT : If you are receiving benefits , there are certain life events that you are required to report. For a complete list , please select the publication below that applies to the type of benefits you receive. NOTE : Failure to report a change may result in an overpayment. What You Need To Know When You Get Retirement Or Survivors Benefits 7 - 13 What You Need To Know When You Get Social Security Disability Benefits 11 - 18 What You Need To Know When You Get Supplemental Security Income SSI 7 - 19

</details>

## h042

**History**

```
Customer: No I don;t need info about that.
Agent: Are you needing information about early or late retirement?
Customer: Yes I am not certain if it is best to start with early retirement or wait a while and start retirement at a later date.
Agent: I can supply you with retirement information for Medicare Beneficiaries which will help you decide what is best for you.
```

**Question.** I want to ask a question relating to Delayed Retirement Credits. What is the income percentage at full retirement age?

**Reference.** your benefitwill be 130.67 percent of your full retirement age benefit

**Answer.** Your Social Security retirement benefit can increase by Delayed Retirement Credits if you delay collecting beyond your full retirement age, and the benefit increase ends when you reach age 70. The context does not provide an “income percentage at full retirement age,” so there’s no specific percentage I can give you from the information provided.

<details><summary>Gold section</summary>

Benefits Planner: Retirement | Applying for Medicare Only | Social Security Administration#2 - Lifetime Benefits We Can Pay On Your Record
Lifetime Benefits We Can Pay On Your Record You can start your retirement benefit at any point from age 62 up until age 70. Your benefit amountwill be higher the longer you delay starting it. This adjustment is usually permanent. If you: Apply for benefits before full retirement age , your benefitswill be reduced because you are taking them earlier. (Full retirement age is 66 for people born between 1943 and 1954. Beginning with 1955, two months are added for every birth year until the full retirement age reaches 67 for people born in 1960 or later.) If your full retirement age is 66 and you decideto start your retirement benefits at age 65 , your benefit will be 93.33 percent of yourfull benefit amount. Delay receiving retirement benefits until after you reach full retirementage any month up to age 70 , you can increase your benefit by accumulating Delayed Retirement Credits. If your full retirement age is 66 and 2 months and you wait until age 70 , your benefitwill be 130.67 percent of your full retirement age benefit. Have family members who qualify for benefits, a delay meansyou would lose some of the benefits they might have received. However , delaying benefitsalso increases the maximum monthly survivors benefit your spouse may receive.

</details>

## h043

**History**

```
Customer: what is a benefits planner?
Agent: do you want to apply for medicare?
Customer: yeah
Agent: Are you are within three months of age 65 or older and not ready to start your monthly Social Security benefits yet?
```

**Question.** thank you

**Reference.** ok great! noproblem.

**Answer.** You should respond to the school’s aid offer within the deadline set by the school, and you can accept the aid you want. Your college or career school will distribute your federal student aid.

<details><summary>Gold section</summary>

Benefits Planner: Retirement | Applying for Medicare Only | Social Security Administration#1 - Applying for Medicare Only
Applying for Medicare Only If you are within three months of age 65 or older and not ready to start your monthly Social Security benefits yet , you can use our online retirement application to sign up just for Medicare and wait to apply for your retirement or spouses benefits later. Before you decide , you need to be sure that you understand how waiting until later will affect : the lifetime benefits we can pay on your account and your health insurance coverage.

</details>

## h044

**History**

```
Customer: Yes, she is eligible on her own.
Agent: She will get her amount first, then if your benefit is higher, we add the difference.
Customer: So she gets the higher amount?
Agent: Yes, we make sure she will receive her maximum possible benefit.
```

**Question.** So when our child turns 16, my spouse's benefits stop?

**Reference.** Yes, unless your spouse is eligible to receive retirement or widow benefits.

**Answer.** Yes, when your child reaches age 16, your spouse’s benefits stop unless your spouse is old enough to receive retirement benefits (age 62 or older) or survivor benefits (as a widow or widower at age 60).

<details><summary>Gold section</summary>

Benefits Planner: Disability | Family Benefits | Social Security Administration#1 - Benefits For Your Spouse
Benefits For Your Spouse When benefits are payable to your spouse : Age 62 or older , unless he or she collects a higher Social Security benefit based on his or her earnings record. The spouse benefit amount will be permanently reduced by a percentage based on the number of months until his or her full retirement age. At any age if he or she is caring for your child under age 16 or disabled. Your spouse would receive these benefits until the child reaches age 16. At that time, the child's benefits continue , but your spouse's benefits stop unless he or she is old enough to receive retirement benefits age 62 or older or survivor benefits as a widow or widower age 60.

</details>

## h045

**History**

```
Customer: Hi there. I would like to get some information related on disability benefits.
Agent: Sure, no problem, we are here to help you to learn about your benefits, and any other doubt you may have.
Agent: have you already received any social security benefit before?
```

**Question.** Yes, I have already receive some of this benefits.

**Reference.** Great. So we can just give you information as well as help you to manage your benefits online.

**Answer.** If you already receive SSI benefits, you should still check whether benefits may be payable on a parent’s earnings record, since higher benefits might be available and you may be entitled to Medicare.

<details><summary>Gold section</summary>

Disability Benefits | Social Security Administration#1 - Disability Benefits
Disability Benefits Learn about Disability Benefits Social Security pays disability benefits to people who can't work because they have a medical condition that's expected to last at least one year or result in death. Find out if you qualify and how Social Security can help you. USE OUR DISABILITY PLANNER Already Receiving Benefits If you receive Social Security disability benefits , you can get information and services for managing your benefits online. MANAGE YOUR BENEFITS If you prefer to complete your application in a language other than English , the online application will give you the option to schedule an appointment to apply for benefits in your preferred language. The online application is currently only available in English. Apply for DisabilityReturn to a Saved ApplicationCheck Application or Appeal Status

</details>

## h046

**History**

```
Customer: Does this mean I could get disability benefits?
Agent: Yes, you may be able to get disability benefits if you've had surgery or received other treatment at a VA hospital, approved hospital, or outpatient center for a disability related to your military service called a service-connected disability.
Customer: Is it enough that I had surgery?
Agent: In this case, the surgery required a recovery time of at least one month or reports show that the surgery or treatment was for a service-connected disability.
```

**Question.** What if my surgery didn't go well and cause severe problems?

**Reference.** If the surgery resulted in severe issues, like surgical wounds that haven't totally healed, and the surgery required a recovery time of at least one month or reports show that the surgery or treatment was for a service-connected disability, then you qualify.

**Answer.** You may be able to get disability benefits if your surgery (for a service-connected disability) led to severe issues such as wounds that haven’t totally healed, being unable to move due to splints or casts, house confinement, or needing a wheelchair or crutches.

<details><summary>Gold section</summary>

Temporary Disability Rating After Surgery Or Cast | Veterans Affairs#1 - Can I get disability benefits from VA?
Can I get disability benefits from VA? You may be able to get disability benefits if you ve had surgery or received other treatment at a VA hospital, approved hospital, or outpatient center for a disability related to your military service called a service - connected disability. If you had surgery , both of these must be true for you : The surgery required a recovery time of at least one month or reports show that the surgery or treatment was for a service - connected disability , and The surgery resulted in severe issues, like : that haven t totally healed Surgical wounds Stumps of recent amputations Being unable to move due to being put in splints or casts to help with healing known as therapeutic immobilizations Being unable to leave your house known as house confinement Being required to use a wheelchair or crutches If you didn t have surgery , this must be true : You had one or more major joints immobilized by a cast.

</details>

## h047

**History**

```
Customer: I wanted to know if I can get loan forgiveness
Agent: Are you employed by a U.S. federal, state, local, or tribal government or not-for-profit organization?
```

**Question.** I'm a state employee

**Reference.** You might be eligible for the Public Service Loan Forgiveness Program

**Answer.** You might be eligible for Public Service Loan Forgiveness (PSLF) if you work full-time for your state employer and make 120 qualifying monthly payments under a qualifying repayment plan on your Direct Loans. To make sure you’re on track, you should submit a Public Service Loan Forgiveness: Employment Certification Form annually or when you change employers.

<details><summary>Gold section</summary>

Public Service Loan Forgiveness | Federal Student Aid#1 - Public Service Loan Forgiveness (PSLF)
Public Service Loan Forgiveness (PSLF) If you are employed by a U.S. federal, state, local, or tribal government or not - for - profit organization , you might be eligible for the Public Service Loan Forgiveness Program. Keep reading to see whether you might qualify. Alert! If your PSLF application is denied because some or all of your payments were not made under a qualifying repayment plan for PSLF , you might still be eligible for forgiveness through Temporary Expanded Public Service Loan Forgiveness. Learn more. The PSLF Program forgives the remaining balance on your Direct Loans after you have made 120 qualifying monthly payments under a qualifying repayment plan while working full - time for a qualifying employer. PSLF Resources Public Service Loan Forgiveness PSLF Help Tool Public Service Loan Forgiveness : Employment Certification Form Public Service Loan Forgiveness : Application for Forgiveness Public Service Loan Forgiveness Program FAQ

</details>

## h048

**History**

```
Customer: What are employment benefits for dependent family members?
Agent: Find out if you re eligible and how to apply to get career and educational counseling through VR&E as the dependent family member of a service member or Veteran with a service - connected disability .
Customer: Can I get Educational and Career Counseling services provided by VR&E (also called Chapter 36)?
Agent: You may be eligible for Educational and Career Counseling if you meet both of the requirements
```

**Question.** I'd also like to learn more about the VA MISSION Act. Are there any care requirements under the VA Mission Act?

**Reference.** Yes there are requirements

**Answer.** Yes. Under the VA MISSION Act, your community care eligibility is based on the new eligibility criteria for community care, and you must be enrolled in VA health care and have received care from VA within the past 24 months to use VA urgent care services.

<details><summary>Gold section</summary>

VA.gov Home | Veterans Affairs#1 - VA MISSION Act
VA MISSION Act Learn about new eligibility criteria for community care under the VA MISSION Act.

</details>

## h049

**History**

```
Customer: Ok, yes, they are good alternatives. I know you ask a lot for birth certificates, but what if you don't have one handy?
Agent: You can go and use the NYS Department of Health Vital Records to lend you a hand on that. You can even order those through an independent partner.
Customer: Going back to those alternate documents, can i use General Educational Development certificate as well?
Agent: Sure. You can contact your college to ask them for a certified copy.
```

**Question.** Are you sure? I don't want to waste my time there.

**Reference.** Absolutely, that document is totally valid for this procedure.

**Answer.** Yes, you can use a General Educational Development (GED) certificate as an equivalent to a high school diploma if you don’t have a diploma. You’ll need to get a certified copy, and you can contact the education department in the state where you graduated or your college to obtain it.

<details><summary>Gold section</summary>

Help finding enough proof of ID#3 - I don t have enough proof of name identification to bring to the DMV. What can I do?
I don t have enough proof of name identification to bring to the DMV. What can I do? You may already have more proof documents than you think , or you may be able to get some proof documents. Here are some suggestions. Bank card debit with your name preprinted on it. Some banks will give you a card the same day you open an account. Online bill printouts. You can print out a copy of a paperless bill. For example , a phone bill, electricity / gas bill, water bill or cable bill. Divorce papers. You can contact your lawyer to find out where to go to obtain the papers, or check with the state where you got divorced. Remember , you must show us the original documents or a certified copy. Duplicate marriage certificate. You can check with the city, town or county where you were married. A lot of localities will allow you to order duplicates online. High school diploma or GED. You can contact the education department in the state where you graduated for a certified copy. If you attended school at a Community College , you may have received a General Educational Development GED certificate. You can contact the college for a certified copy. U.S. college transcripts. You can order these from a college or university you attended, even if you did not graduate there. You will need to have a photo ID from the college. Work ID , paystub or a W2 from state. These documents do not have to be from New York and they do not have to be current. Union card. The card can be from another state. If you lost the card , you can ask the union for help getting a duplicate. Even if you no longer have that union job , you may be a member for life. Life insurance policy. Check with your parents or spouse if they ever had a life insurance policy in your name. The policy must be in effect for at least 2 years. Check cashing card from a supermarket chain with your name printed on it.

</details>

## h050

**History**

```
Customer: not
Agent: Unfortunately, no relevant information is found.
Customer: you want to exchange in an office and keep your Standard document type?
Agent: for that you must follow some steps
```

**Question.** explain me first

**Reference.** You can exchange a New York State driver license or learner permit that is current or that expired within the last 2 years for a New York State non - driver ID card NDID .

**Answer.** To exchange your New York State driver license for a non-driver ID card, you must apply by mail or in a DMV office, and you must use a driver license or learner permit that is current or expired within the last 2 years.

<details><summary>Gold section</summary>

Exchange a NY State driver license for a non-driver ID card#1 - Exchange a NY State driver license for a non-driver ID card[1]
Exchange a NY State driver license for a non-driver ID card[1] You can exchange a New York State driver license or learner permit that is current or that expired within the last 2 years for a New York State non - driver ID card NDID. You must apply by mail or in a DMV office.

</details>

## h051

**History**

```
Customer: Oh i see, what can you tell me about other benefits and services?
Agent: Well, you have the VA transition assistance for when you go out of the active duty life.
Customer: Then i could have access to those earlier benefits, isn't?
Agent: That's correct, like i said, many benefits.
```

**Question.** What can i do managing my benefits?

**Reference.** You can apply to restore your BI Bill benefits if your school is closed or ended for a change.

**Answer.** You can manage your benefits over time by using the VA services available for disability compensation. If you’re managing an insurance plan, you can use your insurance provider’s website to manage your plan and benefits online.

<details><summary>Gold section</summary>

VA Education Benefits | Veterans Affairs#2 - Manage your Veterans education benefits
Manage your Veterans education benefits View your VA payment historySee your payment history for VA education and other benefits you may have like disability compensation and pension. Check your Post-9/11 GI Bill benefitsSee how much of your GI Bill benefits you have left to help pay for school or training. Transfer Post-9/11 GI Bill benefitsTransfer your unused Post-9/11 GI Bill benefits to your spouse or other dependents. Change your GI Bill school or programRequest a change to use a different GI Bill program or to transfer your benefits to a new school or training program. Change your VA direct deposit informationFind out how to change your GI Bill direct deposit and contact information. Check your VA appeal statusTrack the status of your VA education benefits appeal. Verify your school enrollmentUse our online verification system called " WAVE " to confirm you're enrolled in an approved school or training program so you keep receiving your education benefits. Apply to restore your GI Bill benefitsIf your school closed or your program ended because of a change in VA regulations or a new law , apply to have your GI Bill benefits restored.

</details>

## h052

**History**

```
Agent: The letter means that your insurance company notified DMV that your insurance coverage ended, and that no other company notified DMV of new coverage.
Agent: and do you have insurance?
Customer: do not
Agent: Unfortunately, no relevant information is found.
```

**Question.** and when would I have to turn in the registration?

**Reference.** If you don't have insurance, you must deliver your vehicle registration and license plates to the DMV immediately.

**Answer.** If you don’t have insurance, you must surrender your vehicle registration and plates to the DMV immediately. Your registration and, if the lapse is 91 days or more, your driver license suspension will be tied to when the lapse period is determined.

<details><summary>Gold section</summary>

Respond to DMV insurance letters and orders#3 - I received a Letter that states my insurance lapsed. What can I do?
I received a Letter that states my insurance lapsed. What can I do? The letter means your insurance company notified the DMV that your insurance coverage ended, and that no other company notified the DMV about new coverage. If you have insurance , follow the instructions in the letter and contact your company or agent about the problem. Ask your company to file a notice of coverage with the DMV electronically. If you don t have insurance , you need to surrender your vehicle registration and plates to the DMV immediately.

</details>

## h053

**History**

```
Customer: but can you start with the resources about what insurance I need?
Agent: Would you like to know more about how much life insurance you need?
Customer: yes I would so I don't overpay
Agent: You can use the life insurance needs calculator and VGLI comparison questionnaire to help you decide how much life insurance you need
```

**Question.** I have another question about Accessing and Managing Your VA Benefits and Care. What can I check about the benefits

**Reference.** You will be ablel to check your Post-9/11 GI Bill benefits; view payment history; or change your current education benefits.

**Answer.** You can check the status of a disability or pension claim and manage your VA health and benefits online through VA.gov if you’re signed up for VA health care. You can also refill prescriptions and send a message to your VA health care provider.

<details><summary>Gold section</summary>

VA.gov Home | Veterans Affairs#1 - Education
Education Check your Post-9/11 GI Bill benefits View your payment history Change your current education benefits Compare GI Bill benefits by school Apply for education benefits

</details>

## h054

**History**

```
Customer: I need more information
Agent: Please contact us by phone or in person to schedule an appointment to complete the SSI application
Customer: To apply for a child
Agent: The report collects information about the child 's disabling condition and how it affects his / her ability to function
```

**Question.** If i do not want to do this report online or i need help

**Reference.** you can call us toll - free at 1 - 800 - 772 - 1213

**Answer.** If you do not want to do the Child Disability Report online or you need help, you can call Social Security toll-free at 1-800-772-1213. If you are deaf or hard of hearing, call the toll-free TTY number 1-800-325-0778.

<details><summary>Gold section</summary>

Apply For A Child (Under Age 18) | Disability Benefits | SSA#1 - Steps to Apply
Steps to Apply REVIEW the Child Disability Starter Kit. This kit answers common questions about applying for Supplemental Security Income SSI benefits for children, and includes a worksheet that will help you gather the information you need. CONTACT Social Security right away to find out whether the income and resources of the parents and the child are within the allowed limits, and to start the SSI application process. FILL OUT the online Child Disability Report. At the end of the report , we will ask you to sign a form that gives the child's doctor permission to give us information about his / her disability. We need this information so that we can make a decision on the child's claim. If you do not want to do this report online or you need help , you can call us toll - free at 1 - 800 - 772 - 1213. If you are deaf or hard - of - hearing , call our toll - free TTY number , 1 - 800 - 325 - 0778. Representatives are available Monday through Friday between 8 a.m. and 5:30 p.m.

</details>

## h055

**History**

```
Customer: Ok, yes, they are good alternatives. I know you ask a lot for birth certificates, but what if you don't have one handy?
Agent: You can go and use the NYS Department of Health Vital Records to lend you a hand on that. You can even order those through an independent partner.
Customer: Going back to those alternate documents, can i use General Educational Development certificate as well?
Agent: Sure. You can contact your college to ask them for a certified copy.
```

**Question.** Are you sure? I don't want to waste my time there.

**Reference.** Absolutely, that document is totally valid for this procedure.

**Answer.** Yes, you can use a General Educational Development (GED) certificate if you need a high school equivalent, but you must provide a certified copy. You can contact the education department in the state where you graduated or your college to get the certified copy.

<details><summary>Gold section</summary>

Help finding enough proof of ID#3 - I don t have enough proof of name identification to bring to the DMV. What can I do?
I don t have enough proof of name identification to bring to the DMV. What can I do? You may already have more proof documents than you think , or you may be able to get some proof documents. Here are some suggestions. Bank card debit with your name preprinted on it. Some banks will give you a card the same day you open an account. Online bill printouts. You can print out a copy of a paperless bill. For example , a phone bill, electricity / gas bill, water bill or cable bill. Divorce papers. You can contact your lawyer to find out where to go to obtain the papers, or check with the state where you got divorced. Remember , you must show us the original documents or a certified copy. Duplicate marriage certificate. You can check with the city, town or county where you were married. A lot of localities will allow you to order duplicates online. High school diploma or GED. You can contact the education department in the state where you graduated for a certified copy. If you attended school at a Community College , you may have received a General Educational Development GED certificate. You can contact the college for a certified copy. U.S. college transcripts. You can order these from a college or university you attended, even if you did not graduate there. You will need to have a photo ID from the college. Work ID , paystub or a W2 from state. These documents do not have to be from New York and they do not have to be current. Union card. The card can be from another state. If you lost the card , you can ask the union for help getting a duplicate. Even if you no longer have that union job , you may be a member for life. Life insurance policy. Check with your parents or spouse if they ever had a life insurance policy in your name. The policy must be in effect for at least 2 years. Check cashing card from a supermarket chain with your name printed on it.

</details>

## h056

**History**

```
Customer: What will you use these documents for?
Agent: We may use one document for two purposes  For example , we may use your U.S. passport as proof of both citizenship and identity
Customer: What if a birth certificate does not exist?
Agent: If a birth certificate does not exist  we may be able to accept your :s
  Religious record made before the age of 5 showing your date of birth ;s
   U.S. hospital record of your birth
```

**Question.** Do you need any other information?

**Reference.** we may ask you for information about the schools you attended or we may ask you to provide copies of tax records that would show you were never assigned a Social Security number

**Answer.** Yes. If you’re requesting an original Social Security number and you’re age 12 or older, you must appear in person for an interview, and we’ll ask for evidence to show that you don’t have a Social Security number.

<details><summary>Gold section</summary>

Learn what documents you will need to get a Social Security Card | Social Security Administration#10 - What original documents do I need?
What original documents do I need? Citizenship We can accept only certain documents as proof of U.S. citizenship. These include a U.S. birth certificate or a U.S. passport. Age You must present your birth certificate. If one exists , you must submit it. If a birth certificate does not exist , we may be able to accept your : Religious record made before the age of 5 showing your date of birth ; U.S. hospital record of your birth ; or U.S. passport. Anyone age 12 or older requesting an original Social Security number must appear in person for an interview. We will ask for evidence to show you do not have a Social Security number. Here are examples of documents you can use to prove a Social Security number was never assigned : If you lived outside the United States for an extended period , a current or previous passport , school and/or employment records , and any other record that would show long - term residence outside the United States could be used to show you do not have a Social Security number. If you have lived in the United States and you are applying for an original Social Security number , we may ask you for information about the schools you attended or we may ask you to provide copies of tax records that would show you were never assigned a Social Security number. Identity We can accept only certain documents as proof of identity. An acceptable document must be current not expired and show your name, identifying information date of birth or age and preferably a recent photograph. For example , as proof of identity Social Security must see your : U.S. driver's license ; State - issued non - driver identification card ; or U.S. passport. If you do not have one of these specific documents or you cannot get a replacement for one of them within 10 days , we will ask to see other documents. Any documents submitted, including the following, must be current not expired and show your name, identifying information date of birth or age and preferably a recent photograph : Employee identification card ; School identification card ; Health insurance card not a Medicare card ; or U.S. military identification card. Note We may use one document for two purposes. For example , we may use your U.S. passport as proof of both citizenship and identity. However , you must provide at least two separate documents.

</details>

## h057

**History**

```
Customer: As for my retirement benefits, is there a limit to what I can earn?
Agent: For 2019 , that limit is $ 17,640
Customer: Are you under full retirement age?
Agent: For 2019 , that limit is $ 17,640
```

**Question.** Will it ever increase?

**Reference.** Higher benefits can be important to you later in life and increase the future benefit amounts your family and your survivors could receive

**Answer.** Your yearly earnings limit can change over time, so it may increase or decrease in the future. If you’re under full retirement age and your earnings are over the limit, your benefits may be reduced.

<details><summary>Gold section</summary>

Benefits Planner: Retirement | Getting Benefits While Working | Social Security Administration#2 - Getting Benefits While Working
Getting Benefits While Working You can work while you receive Social Security retirement or survivors benefits. When you do , it could mean a higher benefit for you in the future. Each year we review the records for all working Social Security recipients. If your earnings for the prior year are higher than one of the years we used to compute your retirement benefit , we will recalculate your benefit amount. We pay the increase retroactive to January the year after you earned the money. Higher benefits can be important to you later in life and increase the future benefit amounts your family and your survivors could receive.

</details>

## h058

**History**

```
Customer: we need help with a complaint
Agent: Do you need help protecting your facility license, registration or certification?
```

**Question.** no I think it's all good we just need some info

**Reference.** Would you like to know what to do if a complaint is filed against you?

**Answer.** To place a complaint against a DMV regulated automotive business, you must submit a completed Vehicle Safety Complaint Report PDF (VS-35) along with any supporting documents to the DMV Consumer & Facilities Services Complaint Unit, and you must first try to resolve the issue with the business’s management while keeping written records. You can contact the Complaint Unit at 1-518-474-8943 (8:30 a.m. to 4:15 p.m., Monday–Friday).

<details><summary>Gold section</summary>

A Guide for Facilities:#3 - What to do if a complaint is filed against you
What to do if a complaint is filed against you The New York State Department of Motor Vehicles regulates all Repair Shops, Inspection Stations, Dealers, Vehicle Dismantlers and other related businesses in NYS. To legally operate as such a business , you must register with DMV. Once your application is approved you will receive a certificate from DMV. A copy of the Commissioner's Regulations that pertain to your type of business may be found on the DMV web site at dmv.ny.gov [1]. They will explain your responsibilities to consumers. You must follow all consumer protection laws and regulations. DMV advises all consumers who have a complaint against a dealer, inspection station, repair shop, or dismantler to make an attempt to resolve their complaint with the business manager. If they are not successful , they are advised to contact the DMV Consumer & Facilities Services Complaint Unit. Protect Your Business : Keep a copy of all work orders in an easy - to - access location.

</details>

## h059

**History**

```
Customer: So when I give them my plates I will get a refund?
Agent: When you surrender your plates ,  your Receipt FS-6 T indicates if you are eligible to receive a refund
Customer: Can you give me an exaplme or an estimate on what my refund will be?
Agent: I sure can!  Here is an example to show how your refund amount is determined .
    You paid $ 137.50 to register your vehicle for two years
```

**Question.** What if I changed my name, is it possible to still get a refund?

**Reference.** Yes it is possible

**Answer.** Yes, you can get a refund if you changed your name. Surrender your vehicle plates at a DMV office and request a transfer receipt, then send the completed and signed Request for Refund MV-215 plus proof of your name change (like your marriage certificate, divorce documents, or other court papers) to the address on MV-215; the DMV will issue your refund in your new name if you’re eligible.

<details><summary>Gold section</summary>

Refunds and transfer credits for surrendered plates#3 - Can I get a refund if I changed my name?
Can I get a refund if I changed my name? Yes. Follow these instructions surrender the vehicle plates at a DMV office and request a transfer receipt, not a refund receipt send these items to the address on the Request for Refund MV-215 form completed and signed Request for Refund [1] MV-215 that prove the name has changed a photocopy of the marriage certificate, the divorce documents or other court papers the transfer receipt The DMV will issue your refund in your new name, if eligible.

</details>

## h060

**History**

```
Customer: What if someone does not want to transfer the record?
Agent: You must deliver the vehicle plates to the DMV
Customer: and should I carry the license?
Agent: is correct you must carry a New York State Driver's License
```

**Question.** What if I don't have any of that evidence?

**Reference.** there are other tests you can present look at other types of tests you can use.

**Answer.** If you don’t have proof of ownership, you must use the Statement of Ownership (PDF) MV-51B or provide other evidence of ownership such as an old registration, an original Manufacturer’s Certificate of Origin, or an original Manufacturer’s Statement of Origin.

<details><summary>Gold section</summary>

How to transfer a registration to another vehicle#3 - Transfer the of a vehicle (buy, sell, or give away)
Transfer the of a vehicle (buy, sell, or give away) See Buy or sell a vehicle transfer ownership [7 ] Cars , trucks , trailers & motorcycles Model year1973 or newer , either NY State Certificate of Title original or certified copy, not a photocopy with the transfer ownership section completed by the seller , or acceptable proof of ownership from another state original or certified copy, not a photocopy Model year 1972 or older , either a NY State Transferable Registration original or certified copy, not a photocopy and bill of sale [8], or acceptable proof of ownership from another state original or certified copy, not a photocopy See acceptable proofs [9] for other vehicles manufactured homes, boats, ATVs, snowmobiles, gifted vehicles, vehicles with deceased owners. Your insurance company will: 1) give you 2 barcoded original NY State Insurance ID cards (see a sample [10]) or provide you with access to your digital electronic NY State Insurance ID Card 2) send an electronic notice of insurance coverage to the DMV (your insurance agent or broker cannot file this notice) Your NY State Insurance ID cards and the electronic notice together verify your coverage. We need both. You must register your vehicle within 180 days of the effective date on your Insurance ID Card. Bring one copy or form of your Insurance ID Card with you. The DMV office will keep the paper card. Keep the other paper card with the vehicle as your proof of insurance. Anyone operating your vehicle must be able to provide proof of insurance. Learn more about NY State Insurance Requirements [11]. You must provide proof of identity and date of birth. You must be at least 16 years old except for ATV and boat registrations. You can use a NY State driver license learner permit , or non - driver ID card that is current or expired less than 2 years as proof of identity and age. If you don t have one of these , see other kinds of proof [12] you can use. You can estimate the registration fees [13] online if the registration is one of these classes PAS - Passenger COM - Commercial RGL - Passenger MOT - Motorcycle ORM - Motorcycle CSP - Commercial ORC - Commercial RGC - Commercial ORG - Passenger SPO - Passenger SRF - Passenger The two vehicles must have the same registration type passenger, commercial, motorcycle.

</details>
