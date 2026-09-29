#!/usr/bin/env python3
"""
RetainIQ Synthetic Data Generator — Indian Motor Insurance
Outputs CSV files into ../data/ for loading into RETAINIQ_DB.RAW
Reproducible: fixed seed=42
"""

import csv, os, random, math
from datetime import date, timedelta, datetime

SEED = 42
random.seed(SEED)

NUM_CUSTOMERS = 500
NUM_POLICIES = 800
NUM_CLAIMS = 300
NUM_INTERACTIONS = 1500
AT_RISK_RATIO = 0.20
REF_DATE = date(2025, 9, 28)
COMPANY = "SecureLife Motor Insurance"

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "data")
os.makedirs(DATA, exist_ok=True)

# ─── Reference Data ───────────────────────────────────────────────
MALE = ['Aarav','Arjun','Vivaan','Aditya','Vihaan','Sai','Reyansh','Ayaan','Krishna',
    'Ishaan','Shaurya','Atharv','Advait','Dhruv','Kabir','Ritvik','Aarush','Kian',
    'Rahul','Amit','Vikram','Suresh','Rajesh','Manoj','Deepak','Sanjay','Anil',
    'Rohit','Karan','Nikhil','Ajay','Pranav','Gaurav','Harsh','Ravi','Mohit',
    'Varun','Sachin','Ashok','Naveen','Pankaj','Rakesh','Dinesh','Vishal','Anand',
    'Vijay','Ramesh','Pradeep','Shivam','Tushar']
FEMALE = ['Saanvi','Aanya','Aadhya','Ananya','Diya','Myra','Sara','Ira','Anika',
    'Prisha','Navya','Pari','Kiara','Avni','Riya','Anvi','Zara','Meera','Aarohi',
    'Priya','Sneha','Pooja','Neha','Kavita','Sunita','Rekha','Swati','Anjali',
    'Divya','Nisha','Shruti','Pallavi','Deepa','Manisha','Komal','Shalini',
    'Preeti','Rashmi','Smita','Tanvi']
LAST = ['Sharma','Verma','Gupta','Singh','Kumar','Patel','Reddy','Nair','Iyer',
    'Menon','Joshi','Desai','Shah','Mehta','Rao','Pillai','Das','Bose','Sen',
    'Ghosh','Tiwari','Pandey','Mishra','Chauhan','Yadav','Thakur','Jain',
    'Agarwal','Saxena','Srivastava','Banerjee','Chatterjee','Mukherjee','Patil',
    'Kulkarni','Deshpande','Hegde','Shetty','Nambiar','Kaur']
LOCS = [
    ('Mumbai','Maharashtra','400'),('Delhi','Delhi','110'),
    ('Bengaluru','Karnataka','560'),('Hyderabad','Telangana','500'),
    ('Chennai','Tamil Nadu','600'),('Pune','Maharashtra','411'),
    ('Ahmedabad','Gujarat','380'),('Kolkata','West Bengal','700'),
    ('Jaipur','Rajasthan','302'),('Lucknow','Uttar Pradesh','226'),
    ('Kochi','Kerala','682'),('Chandigarh','Punjab','160'),
    ('Indore','Madhya Pradesh','452'),('Coimbatore','Tamil Nadu','641'),
    ('Nagpur','Maharashtra','440'),('Bhopal','Madhya Pradesh','462'),
    ('Visakhapatnam','Andhra Pradesh','530'),('Patna','Bihar','800'),
    ('Surat','Gujarat','395'),('Thiruvananthapuram','Kerala','695'),
]
LANGS = {'Maharashtra':'Marathi','Delhi':'Hindi','Karnataka':'Kannada',
    'Telangana':'Telugu','Tamil Nadu':'Tamil','Gujarat':'Gujarati',
    'West Bengal':'Bengali','Rajasthan':'Hindi','Uttar Pradesh':'Hindi',
    'Kerala':'Malayalam','Punjab':'Hindi','Madhya Pradesh':'Hindi',
    'Andhra Pradesh':'Telugu','Bihar':'Hindi'}

VEHICLES = {
    'Two Wheeler': [
        ('Hero','Splendor Plus',70000),('Honda','Activa 6G',80000),
        ('Bajaj','Pulsar 150',110000),('TVS','Apache RTR 160',120000),
        ('Royal Enfield','Classic 350',200000),('Suzuki','Access 125',85000),
        ('Yamaha','FZ-S V3',115000),('Hero','Glamour',85000),
    ],
    'Car': [
        ('Maruti Suzuki','Swift',650000),('Maruti Suzuki','Baleno',750000),
        ('Hyundai','i20',750000),('Hyundai','Creta',1200000),
        ('Tata','Nexon',850000),('Tata','Punch',600000),
        ('Honda','City',1200000),('Kia','Seltos',1150000),
        ('Kia','Sonet',850000),('Maruti Suzuki','Brezza',850000),
        ('Toyota','Innova Crysta',2000000),('Mahindra','XUV700',1500000),
    ],
    'Commercial': [
        ('Tata','Ace Gold',450000),('Mahindra','Bolero Pickup',850000),
        ('Ashok Leyland','Dost',750000),('Eicher','Pro 2049',1500000),
    ],
}
CLAIM_CATS = ['Accident','Theft','Natural Disaster','Third Party Liability',
    'Windshield Damage','Fire','Roadside Assistance']
PAY_METHODS = ['UPI','Net Banking','Credit Card','Debit Card','Auto Debit','Cash']
AGENTS = ['Priya S.','Arun K.','Meera R.','Raj M.','Divya P.',
    'Sameer T.','Anita G.','Vikram D.','Neha J.','Rohit B.']
REJECT_REASONS = [
    'Claim filed after the stipulated 48-hour reporting window',
    'Policy was in lapsed state at the time of incident',
    'Damage not covered under Third Party Only plan',
    'Incomplete documentation: FIR copy missing',
    'Pre-existing damage detected during surveyor inspection',
    'Vehicle used for commercial purposes under personal policy',
    'Driver did not possess a valid driving licence',
    'Incident occurred while driving under influence of alcohol',
    'Repairs done at unauthorized garage without prior approval',
    'Claim amount exceeds the Insured Declared Value (IDV)',
]

# ─── Transcript Templates ─────────────────────────────────────────
# Each is a format string. Keys: name, full_name, agent, company, tod,
# policy_id, premium, vehicle, claim_id, claim_amount, claim_date,
# category, rejection_reason, overdue_count, overdue_amount, renewal_date

T_CLAIM_COMPLAINT = [
    "Agent: Good {tod}, this is {agent} from {company}. Am I speaking with {name}? "
    "Customer: Yes. I want to know why my claim {claim_id} was rejected. "
    "Agent: Let me check. The claim was filed on {claim_date} for Rs. {claim_amount} regarding {category}. "
    "Customer: I submitted every document you asked for. The rejection reason makes no sense. "
    "Agent: The noted reason is: {rejection_reason}. I understand this is frustrating. "
    "Customer: Frustrating? This is unacceptable. I will escalate to IRDAI if this is not reversed within a week.",

    "Agent: Hello, {agent} from {company}. Is this {name}? "
    "Customer: Yes, and I am very upset. My claim {claim_id} for Rs. {claim_amount} was rejected. "
    "Agent: I see the claim dated {claim_date} for {category}. Let me review it. "
    "Customer: Your surveyor gave a wrong report. {rejection_reason} - that is simply not true. "
    "Agent: I will escalate this to our senior claims officer for a re-evaluation. "
    "Customer: Do it fast. I am already talking to HDFC Ergo and Bajaj Allianz for quotes.",

    "Agent: Good {tod}, this is {agent} calling from {company}. May I speak with {name}? "
    "Customer: Speaking. Look, I have called three times about claim {claim_id}. Nobody helps me. "
    "Agent: I sincerely apologise for the experience. Your claim for Rs. {claim_amount} shows: {rejection_reason}. "
    "Customer: My {vehicle} is sitting in the garage for weeks. I need this resolved now or I am cancelling everything.",
]

T_CLAIM_SETTLED = [
    "Agent: Good {tod}, {name}. This is {agent} from {company}. I am calling to confirm that your claim "
    "{claim_id} for Rs. {claim_amount} has been settled. The amount has been transferred to your bank account. "
    "Customer: Oh, that is great news! Thank you so much. The process was smooth this time. "
    "Agent: We are glad to hear that. Is there anything else I can help you with? "
    "Customer: No, that is all. I am happy with the service. Thank you.",

    "Customer: Hi, I just received the settlement for claim {claim_id}. Rs. {claim_amount} credited. "
    "Agent: Yes {name}, glad to confirm. Your {category} claim has been fully processed. "
    "Customer: Excellent. I appreciate the quick turnaround. Will definitely renew my policy.",
]

T_PAYMENT_COMPLAINT = [
    "Agent: Good {tod}, this is {agent} from {company}. Am I speaking with {name}? "
    "Customer: Yes. What is it? "
    "Agent: I am calling regarding your policy {policy_id}. We notice {overdue_count} overdue payment(s) "
    "totalling Rs. {overdue_amount}. "
    "Customer: I know, I have been having some financial difficulties. The premium of Rs. {premium} is too high. "
    "Agent: I understand. We can discuss flexible payment options. Would you like to switch to quarterly payments? "
    "Customer: Maybe. But honestly I am thinking of not renewing at all. It is too expensive.",

    "Customer: I keep getting SMS reminders about overdue payments for policy {policy_id}. "
    "Agent: Yes {name}, there are {overdue_count} pending payments of Rs. {overdue_amount} total. "
    "Customer: Your auto-debit failed twice and now you are charging me late fees. This is your system error. "
    "Agent: Let me check the transaction logs. I can see the auto-debit attempts were declined by your bank. "
    "Customer: Fine, but waive the late fees at least. Otherwise I will let the policy lapse.",
]

T_CANCELLATION = [
    "Customer: I want to cancel my policy {policy_id} immediately. "
    "Agent: I am sorry to hear that, {name}. May I ask the reason? "
    "Customer: Your claim service is terrible. My claim {claim_id} was rejected unfairly, I have overdue "
    "payment issues, and nobody follows up. I am done with {company}. "
    "Agent: I understand your frustration. Let me connect you with our retention team who can review your "
    "concerns and possibly offer a resolution. "
    "Customer: I have given enough chances. Just process the cancellation.",

    "Customer: Hello, I would like to cancel policy {policy_id} for my {vehicle}. "
    "Agent: {name}, I am sorry to hear this. Can I understand what went wrong? "
    "Customer: I found much better rates with ICICI Lombard. Your premium of Rs. {premium} is not competitive. "
    "Agent: We do have loyalty discounts and NCB benefits. Shall I check what we can offer? "
    "Customer: I already compared. Please just cancel it.",
]

T_RENEWAL_INQUIRY = [
    "Customer: Hi, my policy {policy_id} is coming up for renewal on {renewal_date}. What is the renewal premium? "
    "Agent: Good {tod}, {name}. Let me check. Your current premium is Rs. {premium}. With your NCB benefits, "
    "the renewal premium would be slightly lower. I will email you the exact quote. "
    "Customer: OK, and can I add zero-depreciation cover this time? "
    "Agent: Absolutely. I will include that in the quote. You should receive it within 24 hours.",

    "Agent: Good {tod}, {name}. This is {agent} from {company}. Your policy {policy_id} for your {vehicle} "
    "is due for renewal on {renewal_date}. Would you like to renew? "
    "Customer: Yes, I am happy with the coverage. Please send me the renewal documents. "
    "Agent: Wonderful. I will process this right away. Thank you for continuing with us.",
]

T_GENERAL_INQUIRY = [
    "Customer: Hi, I have a question about my motor insurance policy {policy_id}. "
    "Agent: Of course, {name}. How can I help? "
    "Customer: Does my comprehensive plan cover windshield damage without affecting my NCB? "
    "Agent: Yes, windshield claims up to Rs. 5,000 are covered under the zero-depreciation add-on "
    "without impacting your No Claim Bonus. "
    "Customer: Perfect, good to know. Thanks.",

    "Customer: I need to update the registration address on my policy {policy_id}. I moved from Delhi to Pune. "
    "Agent: Sure {name}, I can help with that. I will need a copy of your new address proof. "
    "Customer: I will email it today. How long does the update take? "
    "Agent: Typically 2-3 working days after we receive the documents.",
]

T_POSITIVE_FEEDBACK = [
    "Customer: I just wanted to call and say thank you. {agent} helped me with my claim last week and "
    "the experience was excellent. Very professional. "
    "Agent: Thank you so much, {name}. We really appreciate your kind words. Is there anything else? "
    "Customer: No, keep up the good work. I have already recommended {company} to my colleagues.",

    "Customer: Hi, I renewed my policy {policy_id} online and the process was very smooth. Just wanted to "
    "give positive feedback. "
    "Agent: Thank you, {name}! We are glad the digital renewal worked well for you. "
    "Customer: Yes, much better than last year. The app has improved a lot.",
]

T_COMPETITOR_MENTION = [
    "Customer: I received a quote from Bajaj Allianz for my {vehicle} that is 20% cheaper than what I pay you. "
    "Agent: {name}, I understand price is important. Let me check if we have any loyalty discounts available "
    "for your policy {policy_id}. Your current premium is Rs. {premium}. "
    "Customer: Please do. If you cannot match it, I will have to switch. "
    "Agent: I will have our retention team call you back with the best possible offer within 48 hours.",

    "Customer: I am comparing motor insurance and {company} seems overpriced. ICICI Lombard and New India "
    "Assurance both quoted lower for the same coverage on my {vehicle}. "
    "Agent: {name}, our plans include benefits like 24x7 roadside assistance and cashless repairs at 5,000+ "
    "garages. But let me see what special rate I can offer for your renewal. "
    "Customer: OK, but the difference needs to be significant for me to stay.",
]

T_PAYMENT_REMINDER_OUT = [
    "Agent: Good {tod}, {name}. This is {agent} from {company}. I am calling to remind you that your premium "
    "payment of Rs. {premium} for policy {policy_id} was due recently. Would you like to make the payment now? "
    "Customer: Oh yes, I forgot. Can I pay through UPI right now? "
    "Agent: Absolutely. I will send you a payment link on WhatsApp. The payment is Rs. {premium}. "
    "Customer: Got it. Let me pay now. Done. "
    "Agent: Payment received. Thank you, {name}. Your policy remains active.",

    "Agent: Hello {name}, this is a courtesy call from {company}. Your policy {policy_id} has an upcoming "
    "payment. We wanted to ensure there are no issues with your auto-debit setup. "
    "Customer: Thanks for checking. I changed my bank account recently. Let me update the auto-debit mandate. "
    "Agent: I can help you with that right now if you have your new bank details handy.",
]

T_EMAIL_COMPLAINT = [
    "Subject: Formal Complaint - Claim {claim_id} Wrongly Rejected\n\n"
    "Dear Sir/Madam,\n\n"
    "I am writing to formally complain about the rejection of my motor insurance claim {claim_id} dated "
    "{claim_date}. The claim was for Rs. {claim_amount} due to {category}. The rejection reason given was: "
    "{rejection_reason}. I find this unacceptable as all required documents including the FIR copy, "
    "photographs, and repair estimate were submitted within the stipulated timeframe.\n\n"
    "I demand an immediate review. If not resolved within 7 working days, I will file a complaint with the "
    "Insurance Ombudsman and IRDAI.\n\nPolicy: {policy_id}\nClaim: {claim_id}\n\n"
    "Regards,\n{full_name}",

    "Subject: Disappointed with Claim Service - Policy {policy_id}\n\n"
    "Dear {company} Team,\n\n"
    "This is regarding my pending claim {claim_id} for {category}. It has been several weeks since I filed "
    "the claim for Rs. {claim_amount} and I have received no proper update. My {vehicle} is still at the "
    "garage and I am bearing daily commute expenses.\n\n"
    "I have been a loyal customer but this experience has been very poor. Please expedite the resolution.\n\n"
    "Regards,\n{full_name}",
]

T_EMAIL_POSITIVE = [
    "Subject: Thank you - Claim {claim_id} Settled\n\n"
    "Dear {company} Team,\n\n"
    "I am writing to thank you for the prompt settlement of my claim {claim_id}. The amount of Rs. "
    "{claim_amount} was credited to my account within the promised timeline. Special thanks to the surveyor "
    "and claims team for the professional handling.\n\nI will definitely continue with {company}.\n\n"
    "Warm regards,\n{full_name}",
]

T_EMAIL_CANCELLATION = [
    "Subject: Request to Cancel Policy {policy_id}\n\n"
    "Dear Sir/Madam,\n\n"
    "I wish to cancel my motor insurance policy {policy_id} for my {vehicle}. My reasons are:\n"
    "1. Premium of Rs. {premium} is not competitive compared to other insurers.\n"
    "2. Poor claim settlement experience.\n"
    "3. Unresponsive customer service.\n\n"
    "Please process the cancellation and refund any applicable pro-rata premium.\n\n"
    "Regards,\n{full_name}",
]

T_WHATSAPP_COMPLAINT = [
    "{name}: Hi, I need help with claim {claim_id}. It was rejected and I disagree with the reason. "
    "Agent: Hello {name}, I am sorry about this. Let me pull up your details. "
    "{name}: The reason given is '{rejection_reason}' but that is wrong. My documents were complete. "
    "Agent: I understand. Let me escalate this for review. You will receive a callback within 24 hours. "
    "{name}: Please make sure someone actually calls this time.",

    "{name}: My policy {policy_id} payment failed again. This is the third time. "
    "Agent: Sorry about that, {name}. Let me check what happened with the auto-debit. "
    "{name}: I have sufficient balance. Your system is broken. Fix it or I am switching. "
    "Agent: I will raise a technical ticket immediately. In the meantime, here is a direct payment link.",
]

T_WHATSAPP_POSITIVE = [
    "{name}: Just received the claim settlement. Thank you! Very quick service this time. "
    "Agent: Glad to hear it, {name}! Is there anything else you need help with? "
    "{name}: No, all good. Will renew my policy next month.",

    "{name}: Hi, I renewed my policy {policy_id} online. Got the documents instantly. Great experience! "
    "Agent: Thank you {name}! Happy to hear the digital process worked well. Drive safe!",
]

TEMPLATES = {
    'claim_complaint_call': T_CLAIM_COMPLAINT,
    'claim_complaint_email': T_EMAIL_COMPLAINT,
    'claim_complaint_whatsapp': T_WHATSAPP_COMPLAINT,
    'claim_settled_call': T_CLAIM_SETTLED,
    'claim_settled_email': T_EMAIL_POSITIVE,
    'claim_settled_whatsapp': T_WHATSAPP_POSITIVE,
    'payment_complaint_call': T_PAYMENT_COMPLAINT,
    'payment_complaint_whatsapp': T_WHATSAPP_COMPLAINT,
    'cancellation_call': T_CANCELLATION,
    'cancellation_email': T_EMAIL_CANCELLATION,
    'competitor_call': T_COMPETITOR_MENTION,
    'renewal_inquiry_call': T_RENEWAL_INQUIRY,
    'general_inquiry_call': T_GENERAL_INQUIRY,
    'positive_feedback_call': T_POSITIVE_FEEDBACK,
    'positive_feedback_whatsapp': T_WHATSAPP_POSITIVE,
    'payment_reminder_call': T_PAYMENT_REMINDER_OUT,
}

def build_transcript(key, ctx):
    from collections import defaultdict
    safe = defaultdict(lambda: 'N/A', ctx)
    ts = TEMPLATES.get(key)
    if not ts:
        base = key.rsplit('_', 1)[0]
        for suffix in ['_call', '_email', '_whatsapp']:
            if base + suffix in TEMPLATES:
                ts = TEMPLATES[base + suffix]
                break
    if not ts:
        ts = T_GENERAL_INQUIRY
    return random.choice(ts).format_map(safe)

# ─── Generators ────────────────────────────────────────────────────

def gen_customers(n=NUM_CUSTOMERS):
    rows = []
    used_emails = set()
    for i in range(1, n + 1):
        gender = random.choices(['Male', 'Female'], weights=[60, 40])[0]
        first = random.choice(MALE if gender == 'Male' else FEMALE)
        last = random.choice(LAST)
        city, state, pin_pre = random.choice(LOCS)
        pin = pin_pre + str(random.randint(100, 999))
        age = random.randint(21, 65)
        # edge cases: ~2% missing age, ~1% missing email
        if random.random() < 0.02:
            age = None
        phone = f"+91{random.randint(7000000000, 9999999999)}"
        email_base = f"{first.lower()}.{last.lower()}{random.randint(1,999)}"
        domain = random.choice(['gmail.com', 'yahoo.co.in', 'outlook.com', 'rediffmail.com'])
        email = f"{email_base}@{domain}"
        while email in used_emails:
            email = f"{email_base}{random.randint(1,99)}@{domain}"
        used_emails.add(email)
        if random.random() < 0.01:
            email = None
        seg = random.choices(['Individual', 'Family', 'Corporate'], weights=[70, 20, 10])[0]
        lang = LANGS.get(state, 'English')
        if random.random() < 0.3:
            lang = 'English'
        rows.append({
            'customer_id': f"C{i:04d}",
            'first_name': first, 'last_name': last, 'age': age,
            'gender': gender, 'city': city, 'state': state,
            'pin_code': pin, 'phone': phone, 'email': email,
            'segment': seg, 'preferred_language': lang,
        })
    return rows

def gen_policies(customers, at_risk_ids, n=NUM_POLICIES):
    rows = []
    cids = [c['customer_id'] for c in customers]
    # ensure every customer gets at least 1 policy
    assigned = list(cids)
    random.shuffle(assigned)
    # remaining slots go to random customers (weighted toward at-risk for more policies)
    extra_pool = cids + [c for c in cids if c in at_risk_ids] * 2
    while len(assigned) < n:
        assigned.append(random.choice(extra_pool))
    random.shuffle(assigned)
    assigned = assigned[:n]

    for i, cid in enumerate(assigned, 1):
        vtype = random.choices(['Two Wheeler', 'Car', 'Commercial'], weights=[30, 55, 15])[0]
        make, model, new_price = random.choice(VEHICLES[vtype])
        vyear = random.randint(2016, 2025)
        depreciation = min(0.8, 0.05 * (2025 - vyear))
        idv = round(new_price * (1 - depreciation), -2)
        ptype = random.choices(['Comprehensive', 'Third Party Only', 'Own Damage'], weights=[65, 25, 10])[0]
        if ptype == 'Third Party Only':
            if vtype == 'Two Wheeler':
                prem = random.randint(482, 1200)
            elif vtype == 'Car':
                prem = random.randint(2100, 7900)
            else:
                prem = random.randint(3000, 12000)
        elif ptype == 'Comprehensive':
            base_rate = random.uniform(0.025, 0.045)
            prem = round(idv * base_rate, -1)
        else:
            base_rate = random.uniform(0.02, 0.035)
            prem = round(idv * base_rate, -1)

        plan = f"{make} {ptype}"
        freq = random.choices(['Annual', 'Half-Yearly', 'Quarterly', 'Monthly'], weights=[60, 20, 12, 8])[0]
        start = REF_DATE - timedelta(days=random.randint(30, 900))
        end = start + timedelta(days=365)
        renewal = end if end >= REF_DATE else end + timedelta(days=365)

        is_risk = cid in at_risk_ids
        if is_risk:
            status = random.choices(['Active', 'Lapsed', 'Cancelled', 'Expired'], weights=[40, 25, 25, 10])[0]
        else:
            status = random.choices(['Active', 'Lapsed', 'Cancelled', 'Expired'], weights=[80, 8, 5, 7])[0]

        ncb = random.choice([0, 0, 20, 25, 35, 45, 50]) if status == 'Active' else 0
        auto_renew = status == 'Active' and random.random() < 0.7

        rows.append({
            'policy_id': f"POL{i:05d}", 'customer_id': cid,
            'product_type': ptype, 'vehicle_type': vtype,
            'vehicle_make': make, 'vehicle_model': model,
            'vehicle_year': vyear, 'plan_name': plan,
            'sum_insured': idv, 'premium_amount': prem,
            'payment_frequency': freq,
            'start_date': str(start), 'end_date': str(end),
            'renewal_date': str(renewal), 'status': status,
            'ncb_percentage': ncb, 'auto_renew': auto_renew,
        })
    return rows

def gen_claims(policies, at_risk_ids, n=NUM_CLAIMS):
    rows = []
    eligible = [p for p in policies if p['product_type'] != 'Third Party Only' or random.random() < 0.3]
    random.shuffle(eligible)
    # at-risk customers more likely to have claims
    risk_pols = [p for p in eligible if p['customer_id'] in at_risk_ids]
    safe_pols = [p for p in eligible if p['customer_id'] not in at_risk_ids]
    pool = risk_pols * 3 + safe_pols
    random.shuffle(pool)

    for i in range(1, n + 1):
        pol = pool[i % len(pool)]
        start = datetime.strptime(pol['start_date'], '%Y-%m-%d').date()
        end = datetime.strptime(pol['end_date'], '%Y-%m-%d').date()
        claim_date = start + timedelta(days=random.randint(10, min(365, (end - start).days)))
        if claim_date > REF_DATE:
            claim_date = REF_DATE - timedelta(days=random.randint(1, 60))

        cat = random.choices(CLAIM_CATS, weights=[35, 15, 10, 15, 10, 5, 10])[0]
        idv = pol['sum_insured']
        if cat in ('Windshield Damage', 'Roadside Assistance'):
            amount = random.randint(1000, 15000)
        elif cat in ('Theft', 'Fire'):
            amount = random.randint(int(idv * 0.3), int(idv * 0.8))
        else:
            amount = random.randint(5000, min(int(idv * 0.5), 500000))

        is_risk = pol['customer_id'] in at_risk_ids
        if is_risk:
            status = random.choices(['Settled', 'Approved', 'Rejected', 'Pending'], weights=[20, 15, 45, 20])[0]
        else:
            status = random.choices(['Settled', 'Approved', 'Rejected', 'Pending'], weights=[45, 25, 15, 15])[0]

        approved = None
        resolution = None
        reject_reason = None
        notes = None

        if status == 'Settled':
            approved = round(amount * random.uniform(0.7, 1.0), 2)
            resolution = claim_date + timedelta(days=random.randint(5, 45))
            notes = 'Claim settled after surveyor assessment.'
        elif status == 'Approved':
            approved = round(amount * random.uniform(0.75, 1.0), 2)
            resolution = claim_date + timedelta(days=random.randint(3, 30))
            notes = 'Approved. Awaiting fund transfer.'
        elif status == 'Rejected':
            reject_reason = random.choice(REJECT_REASONS)
            resolution = claim_date + timedelta(days=random.randint(7, 60))
            notes = f'Rejected: {reject_reason}'
        else:
            if is_risk:
                notes = 'Pending review for over 30 days. Customer has escalated.'
            else:
                notes = 'Under review by claims team.'

        rows.append({
            'claim_id': f"CLM{i:05d}", 'policy_id': pol['policy_id'],
            'customer_id': pol['customer_id'], 'claim_date': str(claim_date),
            'claim_amount': amount, 'approved_amount': approved,
            'status': status, 'category': cat,
            'resolution_date': str(resolution) if resolution else None,
            'rejection_reason': reject_reason, 'notes': notes,
        })
    return rows

def gen_payments(policies, at_risk_ids):
    rows = []
    pid = 0
    freq_months = {'Annual': 12, 'Half-Yearly': 6, 'Quarterly': 3, 'Monthly': 1}

    for pol in policies:
        months = freq_months.get(pol['payment_frequency'], 12)
        start = datetime.strptime(pol['start_date'], '%Y-%m-%d').date()
        end = datetime.strptime(pol['end_date'], '%Y-%m-%d').date()
        prem = pol['premium_amount']
        installment = round(prem / (12 / months), 2)
        is_risk = pol['customer_id'] in at_risk_ids

        d = start
        while d <= min(end, REF_DATE):
            pid += 1
            due = d
            if is_risk:
                st = random.choices(['Paid', 'Overdue', 'Failed', 'Pending'], weights=[45, 30, 15, 10])[0]
            else:
                st = random.choices(['Paid', 'Overdue', 'Failed', 'Pending'], weights=[82, 8, 3, 7])[0]

            paid_date = None
            late_fee = 0
            method = None
            if st == 'Paid':
                delay = random.randint(-2, 5) if not is_risk else random.randint(-2, 20)
                paid_date = due + timedelta(days=delay)
                if delay > 3:
                    late_fee = round(installment * 0.02 * max(1, delay // 7), 2)
                method = random.choices(PAY_METHODS, weights=[35, 20, 15, 10, 15, 5])[0]
            elif st == 'Overdue':
                if random.random() < 0.3:
                    paid_date = due + timedelta(days=random.randint(15, 60))
                    late_fee = round(installment * 0.05, 2)
                    method = random.choices(PAY_METHODS, weights=[35, 20, 15, 10, 15, 5])[0]
            elif st == 'Failed':
                method = random.choice(['Auto Debit', 'Net Banking', 'Credit Card'])

            rows.append({
                'payment_id': f"PAY{pid:06d}", 'policy_id': pol['policy_id'],
                'customer_id': pol['customer_id'], 'due_date': str(due),
                'paid_date': str(paid_date) if paid_date else None,
                'amount': installment, 'status': st,
                'payment_method': method, 'late_fee': late_fee,
            })
            d += timedelta(days=months * 30)
    return rows

def gen_interactions(customers, policies, claims, payments, at_risk_ids, n=NUM_INTERACTIONS):
    rows = []
    cust_map = {c['customer_id']: c for c in customers}
    cpol = {}
    for p in policies:
        cpol.setdefault(p['customer_id'], []).append(p)
    cclm = {}
    for c in claims:
        cclm.setdefault(c['customer_id'], []).append(c)
    cpay = {}
    for p in payments:
        cpay.setdefault(p['customer_id'], []).append(p)

    cids = [c['customer_id'] for c in customers]
    risk_cids = [c for c in cids if c in at_risk_ids]
    safe_cids = [c for c in cids if c not in at_risk_ids]

    def make_ctx(cust, pol=None, clm=None, pays=None):
        overdue = [p for p in (pays or []) if p['status'] in ('Overdue', 'Failed')]
        return {
            'name': cust['first_name'], 'full_name': f"{cust['first_name']} {cust['last_name']}",
            'agent': random.choice(AGENTS), 'company': COMPANY,
            'tod': random.choice(['morning', 'afternoon', 'evening']),
            'policy_id': pol['policy_id'] if pol else 'N/A',
            'premium': f"{pol['premium_amount']:,.0f}" if pol else 'N/A',
            'vehicle': f"{pol['vehicle_make']} {pol['vehicle_model']}" if pol else '',
            'renewal_date': pol['renewal_date'] if pol else 'N/A',
            'claim_id': clm['claim_id'] if clm else 'N/A',
            'claim_amount': f"{clm['claim_amount']:,.0f}" if clm else 'N/A',
            'claim_date': clm['claim_date'] if clm else 'N/A',
            'category': clm['category'] if clm else 'N/A',
            'rejection_reason': (clm.get('rejection_reason') or 'under review') if clm else 'N/A',
            'overdue_count': str(len(overdue)),
            'overdue_amount': f"{sum(p['amount'] for p in overdue):,.0f}" if overdue else '0',
        }

    iid = 0
    for i in range(n):
        # 35% of interactions come from at-risk customers
        if random.random() < 0.35 and risk_cids:
            cid = random.choice(risk_cids)
        else:
            cid = random.choice(cids)

        cust = cust_map[cid]
        is_risk = cid in at_risk_ids
        my_pols = cpol.get(cid, [])
        my_clms = cclm.get(cid, [])
        my_pays = cpay.get(cid, [])
        pol = random.choice(my_pols) if my_pols else None

        # pick scenario
        if is_risk:
            rejected = [c for c in my_clms if c['status'] == 'Rejected']
            pending = [c for c in my_clms if c['status'] == 'Pending']
            overdue = [p for p in my_pays if p['status'] in ('Overdue', 'Failed')]
            if rejected and random.random() < 0.4:
                scenario, channel = 'claim_complaint', random.choices(['call','email','whatsapp'], weights=[50,30,20])[0]
                clm = random.choice(rejected)
            elif overdue and random.random() < 0.3:
                scenario, channel = 'payment_complaint', random.choices(['call','whatsapp'], weights=[70,30])[0]
                clm = None
            elif random.random() < 0.2:
                scenario, channel = 'cancellation', random.choices(['call','email'], weights=[60,40])[0]
                clm = random.choice(rejected) if rejected else (random.choice(my_clms) if my_clms else None)
            elif random.random() < 0.3:
                scenario, channel = 'competitor', 'call'
                clm = None
            else:
                scenario, channel = random.choice(['renewal_inquiry','general_inquiry']), 'call'
                clm = None
        else:
            settled = [c for c in my_clms if c['status'] in ('Settled', 'Approved')]
            if settled and random.random() < 0.25:
                scenario, channel = 'claim_settled', random.choices(['call','email','whatsapp'], weights=[40,30,30])[0]
                clm = random.choice(settled)
            elif random.random() < 0.2:
                scenario, channel = 'positive_feedback', random.choices(['call','whatsapp'], weights=[60,40])[0]
                clm = None
            elif random.random() < 0.15:
                scenario = 'payment_reminder'
                channel = 'call'
                clm = None
            else:
                scenario = random.choice(['renewal_inquiry', 'general_inquiry', 'general_inquiry'])
                channel = random.choice(['call', 'call', 'email'])
                clm = None

        ctx = make_ctx(cust, pol, clm, my_pays)
        key = f"{scenario}_{channel}"
        content = build_transcript(key, ctx)
        # strip newlines for CSV safety, keep as sentence flow
        content = content.replace('\n\n', ' ').replace('\n', ' ')

        direction = 'Outbound' if scenario == 'payment_reminder' else 'Inbound'
        channel_display = {'call': 'Call', 'email': 'Email', 'whatsapp': 'WhatsApp', 'chat': 'Chat'}[channel]

        days_ago = random.randint(0, 365)
        ts = REF_DATE - timedelta(days=days_ago)
        hour = random.randint(9, 18)
        minute = random.randint(0, 59)
        ts_str = f"{ts} {hour:02d}:{minute:02d}:00"

        subject = None
        if channel == 'email' and 'Subject:' in content:
            parts = content.split('Subject:', 1)
            rest = parts[1]
            if '\n' in rest:
                subj_line, body = rest.split('\n', 1)
                subject = subj_line.strip()
                content = body.strip()
            elif '  ' in rest:
                subj_line, body = rest.split('  ', 1)
                subject = subj_line.strip()
                content = body.strip()

        iid += 1
        rows.append({
            'interaction_id': f"INT{iid:06d}", 'customer_id': cid,
            'channel': channel_display, 'direction': direction,
            'interaction_ts': ts_str, 'subject': subject,
            'content': content, 'summary': None, 'sentiment_score': None,
        })

    return rows

# ─── Writers ───────────────────────────────────────────────────────

def write_csv(path, headers, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  CSV: {os.path.basename(path)} -> {len(rows)} rows")

def sql_val(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return 'NULL'
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"

def write_insert_sql(filepath, table, columns, rows, batch_size=500):
    batches = []
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        vals = []
        for r in batch:
            v = ', '.join(sql_val(r.get(c)) for c in columns)
            vals.append(f"({v})")
        sql = f"INSERT INTO RETAINIQ_DB.RAW.{table}\n({', '.join(c.upper() for c in columns)})\nVALUES\n"
        sql += ',\n'.join(vals) + ';\n'
        batches.append(sql)

    with open(filepath, 'w', encoding='utf-8') as f:
        for b in batches:
            f.write(b)
            f.write('\n')
    print(f"  SQL: {os.path.basename(filepath)} -> {len(rows)} rows in {len(batches)} batch(es)")
    return batches

# ─── Main ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("RetainIQ Synthetic Data Generator")
    print(f"Seed: {SEED}  |  Ref date: {REF_DATE}")
    print("=" * 60)

    # 1. Customers
    print("\n[1/5] Generating customers...")
    customers = gen_customers()
    at_risk_ids = set(c['customer_id'] for c in customers[:int(len(customers) * AT_RISK_RATIO)])
    print(f"  Total: {len(customers)}, At-risk: {len(at_risk_ids)}")

    cust_cols = ['customer_id','first_name','last_name','age','gender','city','state',
                 'pin_code','phone','email','segment','preferred_language']
    write_csv(os.path.join(DATA, 'customers.csv'), cust_cols, customers)

    # 2. Policies
    print("\n[2/5] Generating policies...")
    policies = gen_policies(customers, at_risk_ids)
    statuses = {}
    for p in policies:
        statuses[p['status']] = statuses.get(p['status'], 0) + 1
    print(f"  Total: {len(policies)}, Statuses: {statuses}")

    pol_cols = ['policy_id','customer_id','product_type','vehicle_type','vehicle_make',
                'vehicle_model','vehicle_year','plan_name','sum_insured','premium_amount',
                'payment_frequency','start_date','end_date','renewal_date','status',
                'ncb_percentage','auto_renew']
    write_csv(os.path.join(DATA, 'policies.csv'), pol_cols, policies)

    # 3. Claims
    print("\n[3/5] Generating claims...")
    claims = gen_claims(policies, at_risk_ids)
    cstatuses = {}
    for c in claims:
        cstatuses[c['status']] = cstatuses.get(c['status'], 0) + 1
    print(f"  Total: {len(claims)}, Statuses: {cstatuses}")

    clm_cols = ['claim_id','policy_id','customer_id','claim_date','claim_amount',
                'approved_amount','status','category','resolution_date',
                'rejection_reason','notes']
    write_csv(os.path.join(DATA, 'claims.csv'), clm_cols, claims)

    # 4. Payments
    print("\n[4/5] Generating payments...")
    payments = gen_payments(policies, at_risk_ids)
    pstatuses = {}
    for p in payments:
        pstatuses[p['status']] = pstatuses.get(p['status'], 0) + 1
    print(f"  Total: {len(payments)}, Statuses: {pstatuses}")

    pay_cols = ['payment_id','policy_id','customer_id','due_date','paid_date',
                'amount','status','payment_method','late_fee']
    write_csv(os.path.join(DATA, 'payments.csv'), pay_cols, payments)

    # 5. Interactions
    print("\n[5/5] Generating interactions...")
    interactions = gen_interactions(customers, policies, claims, payments, at_risk_ids)
    channels = {}
    for ix in interactions:
        channels[ix['channel']] = channels.get(ix['channel'], 0) + 1
    print(f"  Total: {len(interactions)}, Channels: {channels}")

    int_cols = ['interaction_id','customer_id','channel','direction','interaction_ts',
                'subject','content','summary','sentiment_score']
    write_csv(os.path.join(DATA, 'interactions.csv'), int_cols, interactions)

    # Generate SQL INSERT files
    print("\n--- Generating SQL INSERT files ---")
    write_insert_sql(os.path.join(DATA, 'insert_customers.sql'), 'CUSTOMERS', cust_cols, customers)
    write_insert_sql(os.path.join(DATA, 'insert_policies.sql'), 'POLICIES', pol_cols, policies)
    write_insert_sql(os.path.join(DATA, 'insert_claims.sql'), 'CLAIMS', clm_cols, claims)
    write_insert_sql(os.path.join(DATA, 'insert_payments.sql'), 'PAYMENTS', pay_cols, payments, batch_size=1000)
    write_insert_sql(os.path.join(DATA, 'insert_interactions.sql'), 'INTERACTIONS', int_cols, interactions, batch_size=500)

    print("\n" + "=" * 60)
    print("DONE. Files written to:", DATA)
    print(f"Customers: {len(customers)}, Policies: {len(policies)}, "
          f"Claims: {len(claims)}, Payments: {len(payments)}, "
          f"Interactions: {len(interactions)}")
    print("=" * 60)

if __name__ == '__main__':
    main()
