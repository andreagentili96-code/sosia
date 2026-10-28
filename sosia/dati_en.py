"""English dictionaries (US and UK): first names, surnames, places, street suffixes, alias pools, common words.

Written by hand, local only. As for Italian: detection lists are broad; alias pools avoid ordinary English words
(no «Baker», «Rose», «Young»), so a restored text never confuses a real word with a fake surname."""
from __future__ import annotations

from .dati import norm

FIRST_M = """James John Robert Michael William David Richard Joseph Thomas Charles Christopher Daniel Matthew Anthony Mark
Donald Steven Paul Andrew Joshua Kenneth Kevin Brian George Timothy Ronald Edward Jason Jeffrey Ryan Jacob Gary Nicholas
Eric Jonathan Stephen Larry Justin Scott Brandon Benjamin Samuel Gregory Alexander Frank Patrick Raymond Jack Dennis
Jerry Tyler Aaron Jose Adam Nathan Henry Douglas Zachary Peter Kyle Ethan Walter Noah Jeremy Christian Keith Roger
Terry Gerald Harold Sean Austin Carl Arthur Lawrence Dylan Jesse Jordan Bryan Billy Joe Bruce Gabriel Logan Albert
Willie Alan Juan Wayne Elijah Randy Roy Vincent Ralph Eugene Russell Bobby Mason Philip Louis Harry Oliver Charlie
Alfie Freddie Archie Leo Oscar Theo Arlo Finley Rory Callum Connor Liam Declan Owen Rhys Gareth Dafydd Ewan Hamish
Angus Fraser Alistair Nigel Graham Trevor Clive Colin Derek Malcolm Neil Ian Stuart Barry Darren Craig Wesley Dwayne
Tyrone Marcus Andre Darnell Jamal DeShawn Malik Luis Carlos Miguel Jorge Diego Alejandro Ricardo Javier Pedro Rafael
Manuel Mohammed Mohamed Muhammad Ahmed Ali Omar Hassan Ibrahim Yusuf Tariq Imran Bilal Rajesh Arjun Vikram Sanjay
Rahul Amit Ravi Wei Ming Jun Hiroshi Kenji Takeshi Minh Duc Tuan Hung Quang Jin Min Sung Hyun Chidi Emeka Oluwaseun
Tunde Kwame Kofi Piotr Tomasz Krzysztof Marek Jakub Andrei Mihai Vlad Ion Bogdan Sergei Dmitri Ivan Nikolai Tobias
Elliot Isaac Caleb Hunter Wyatt Grayson Jaxon Lincoln Asher Ezra Silas Miles Jasper Felix Hugo Rufus Barnaby Jake
Joel Luke Ben Tom Tim Sam Dan Matt Mike Rob Bob Bill Jim Jimmy Tony Steve Pete Nick Chris Andy Dave Joey""".split()

FIRST_F = """Mary Patricia Jennifer Linda Elizabeth Barbara Susan Jessica Sarah Karen Lisa Nancy Betty Margaret Sandra Ashley
Kimberly Emily Donna Michelle Carol Amanda Dorothy Melissa Deborah Stephanie Rebecca Sharon Laura Cynthia Kathleen Amy
Angela Shirley Anna Brenda Pamela Emma Nicole Helen Samantha Katherine Christine Debra Rachel Carolyn Janet Catherine
Maria Heather Diane Ruth Julie Olivia Joyce Virginia Victoria Kelly Lauren Christina Joan Evelyn Judith Megan Andrea
Cheryl Hannah Jacqueline Martha Gloria Teresa Ann Sara Madison Frances Kathryn Janice Jean Abigail Alice Judy Sophia
Grace Denise Amber Doris Marilyn Danielle Beverly Isabella Theresa Diana Natalie Brittany Charlotte Marie Kayla Alexis
Lori Amelia Isla Ava Mia Poppy Ella Lily Freya Florence Evie Phoebe Imogen Harriet Eleanor Beatrice Matilda Ruby Daisy
Siobhan Niamh Aoife Ciara Sinead Mairead Fiona Morag Kirsty Ailsa Bethan Cerys Nia Gwen Sian Rhiannon Tracey Sharon
Lorraine Wendy Gillian Shona Kerry Leanne Gemma Jade Chantelle Keisha Latoya Tamika Shanice Aaliyah Imani Destiny
Jasmine Maya Sofia Camila Valentina Lucia Ximena Guadalupe Rosa Carmen Elena Ana Fatima Aisha Amina Zainab Mariam
Leila Yasmin Noor Priya Ananya Deepa Sunita Kavya Mei Ling Yan Xin Hana Yuki Sakura Linh Lan Thao Hoa Ji Soo Min
Ngozi Chiamaka Adaeze Folake Ama Abena Agnieszka Katarzyna Malgorzata Ewa Joanna Ioana Elena Natalia Olga Svetlana
Tatiana Oksana Chloe Zoe Ellie Molly Millie Sophie Lucy Katie Jess Kate Liz Beth Meg Jen Sue Kim Pam Deb Becky Abby""".split()

SURNAMES = """Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez Hernandez Lopez Gonzalez Wilson
Anderson Thomas Taylor Moore Jackson Martin Lee Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker
Young Allen King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson Baker Hall Rivera Campbell Mitchell Carter
Roberts Gomez Phillips Evans Turner Diaz Parker Cruz Edwards Collins Reyes Stewart Morris Morales Murphy Cook Rogers
Gutierrez Ortiz Morgan Cooper Peterson Bailey Reed Kelly Howard Ramos Kim Cox Ward Richardson Watson Brooks Chavez Wood
James Bennett Gray Mendoza Ruiz Hughes Price Alvarez Castillo Sanders Patel Myers Long Ross Foster Jimenez Powell
Jenkins Perry Russell Sullivan Bell Coleman Butler Henderson Barnes Gonzales Fisher Vasquez Simmons Romero Jordan
Patterson Alexander Hamilton Graham Reynolds Griffin Wallace Moreno West Cole Hayes Bryant Herrera Gibson Ellis Tran
Medina Aguilar Stevens Murray Ford Castro Marshall Owens Harrison Fernandez McDonald Woods Washington Kennedy Wells
Vargas Henry Chen Freeman Webb Tucker Guzman Burns Crawford Olson Simpson Porter Hunter Gordon Mendez Silva Shaw Snyder
Mason Dixon Munoz Hunt Hicks Holmes Palmer Wagner Black Robertson Boyd Rose Stone Salazar Fox Warren Mills Meyer Rice
Schmidt Garza Daniels Ferguson Nichols Stephens Soto Weaver Ryan Gardner Payne Grant Dunn Kelley Spencer Hawkins Arnold
Pierce Vazquez Hansen Peters Santos Hart Bradley Knight Elliott Cunningham Duncan Armstrong Hudson Carroll Lane Riley
Andrews Alvarado Ray Delgado Berry Perkins Hoffman Johnston Matthews Pena Richards Contreras Willis Carpenter Lawrence
Sandoval Guerrero George Chapman Rios Estrada Ortega Watkins Greene Nunez Wheeler Valdez Harper Burke Larson Santiago
Maldonado Morrison Franklin Carlson Austin Dominguez Carr Lawson Jacobs Obrien Lynch Singh Vega Bishop Montgomery
Oliver Jensen Harvey Williamson Gilbert Dean Sims Espinoza Howell Li Wong Reid Hanson Le McCoy Garrett Burton Fuller
Wang Weber Welch Rojas Lucas Marquez Fields Park Yang Little Banks Padilla Day Walsh Bowman Schultz Luna Fowler Mejia
Davidson Acosta Brewer May Holland Juarez Newman Pearson Curtis Cortez Douglas Schneider Joseph Barrett Navarro Figueroa
Keller Avila Wade Molina Stanley Hopkins Campos Barnett Bates Chambers Caldwell Beck Lambert Miranda Byrd Craig Ayala
Lowe Frazier Powers Neal Leonard Gregory Carrillo Sutton Fleming Rhodes Shelton Schwartz Norris Jennings Watts Duran
Walters Cohen McDaniel Moran Parks Steele Vaughn Becker Holt DeLeon Barker Terry Hale Leon Hail Benson Haynes Horton
Miles Lyons Pham Graves Bush Thornton Wolfe Warner Cabrera McKinney Mann Zimmerman Dawson Lara Fletcher Page McCarthy
Love Robles Cervantes Solis Erickson Reeves Chang Klein Salinas Fuentes Baldwin Daniel Simon Velasquez Hardy Higgins
Aguirre Lin Cummings Chandler Sharp Barber Bowen Ochoa Dennis Robbins Liu Ramsey Francis Griffith Paul Blair OConnor
Cardenas Pacheco Cross Calderon Quinn Moss Swanson Chan Rivas Khan Rodgers Serrano Fitzgerald Rosales Stevenson
Christensen Manning Gill Curry McLaughlin Harmon McGee Gross Doyle Garner Newton Burgess Reese Walton Blake Trujillo
Adkins Brady Goodman Roman Webster Goodwin Fischer Huang Potter Delacruz Montoya Todd Wu Hines Mullins Castaneda
Malone Cannon Tate Mack Sherman Hubbard Hodges Zhang Guerra Wolf Valencia Saunders Franco Rowe Gallagher Farmer Hammond
Hampton Townsend Ingram Wise Gallegos Clarke Barton Schroeder Maxwell Waters Logan Camacho Strickland Norman Person
Colon Parsons Frank Harrington Glover Osborne Buchanan Casey Floyd Patton Ibarra Ball Tyler Suarez Bowers Orozco
Salas Cobb Gibbs Andrade Bauer Conner Moody Escobar McGuire Lloyd Mueller Hartman French Kramer McBride Pope Lindsey
Velazquez Norton McCormick Sparks Flynn Yates Hogan Marsh Macias Villanueva Zamora Pratt Stokes Owen Ballard Lang
Brock Villarreal Charles Drake Barrera Cain Patrick Pineda Burnett Mercado Santana Shepherd Bautista Ali Shaffer Lamb
Trevino McKenzie Hess Beil Olsen Cochran Morton Nash Wilkins Petersen Briggs Shah Roth Nicholson Holloway Lozano
Flowers Rangel Hoover Short Arias Mora Valenzuela Bryan Meyers Weiss Underwood Bass Greer Summers Houston Carson
Morrow Clayton Whitaker Decker Yoder Collier Zuniga Carey Wilcox Melendez Poole Roberson Larsen Conley Davenport
Copeland Massey Lam Huff Rocha Cameron Jefferson Hood Monroe Anthony Pittman Huynh Randall Singleton Kirk Combs Mathis
Christian Skinner Bradford Richard Galvan Wall Boone Kirby Wilkinson Bridges Bruce Atkinson Velez Meza Roy Vincent York
Hodge Villa Abbott Allison Tapia Gates Chase Sosa Sweeney Farrell Wyatt Dalton Horn Barron Phelps Yu Dickerson Heath
Foley Atkins Mathews Bonilla Acevedo Benitez Zavala Hensley Glenn Cisneros Harrell Shields Rubio Choi Huffman Boyer
Garrison Arroyo Bond Kane Hancock Callahan Dillon Cline Wiggins Grimes Arellano Melton O'Neill Savage Ho Beltran
Pitts Parrish Ponce Rich Booth Koch Golden Ware Brennan McDowell Marks Cantu Humphrey Baxter Sawyer Clay Tanner
Hutchinson Kaur Berg Wiley Gilmore Russo Villegas Hobbs Keith Wilkerson Ahmed Beard McClain Montes Mata Rosario
Vang Walter Henson O'Brien O'Connor O'Neil MacLeod MacDonald MacKenzie McIntyre Fitzpatrick Kowalski Nowak Wisniewski
Okafor Okonkwo Adeyemi Mensah Asante Kaur Gupta Sharma Kumar Reddy Nair Iyer Desai Mehta Chowdhury Rahman Hussain
Akhtar Begum Iqbal Malik Butt Siddiqui Nakamura Tanaka Suzuki Watanabe Yamamoto Sato Kobayashi Pham Vu Dang Bui Do
Hoang Ngo Duong Lim Teo Tan Ng Goh Popescu Ionescu Popa Petrov Ivanov Kuznetsov Smirnov Kovacs Nagy Novak Horvat""".split()

# Surnames that are ordinary words: extra evidence needed when they appear alone.
SURNAME_WORDS = {norm(x) for x in """Baker Young King Wright Scott Hill Green Hall Rivera Carter Turner Parker Cook Brooks Wood
Gray Price Long Ross Fisher Jordan Graham Wallace West Cole Gibson Ford Marshall Washington Kennedy Wells Henry Freeman
Hunter Gordon Shaw Mason Hunt Black Rose Stone Fox Warren Mills Rice Grant Dunn Spencer Hart Knight Lane Ray Berry
Lawrence George Day Little Banks May Holland Newman Page Love Simon Hardy Sharp Barber Cross Moss Quinn Gross Wolf
Farmer Wise Waters Norman Person Frank Ball Glover Bowers Pope Marsh Lamb Short Bass Summers Clay Tanner Rich Golden
Booth Marks Baxter Sawyer Savage Bond Kane Glenn Hood Kirk Wall Chase Horn Mathis Christian Bishop Fields Bell Brown
White Young Long Major Joy Hope Faith Bird Fish Fowler Shepherd Mann Small Strong Sweet Swift Wise""".split()}

# Places: (name, state or county, ZIP or postcode)
US_CITIES = [("New York", "NY", "10001"), ("Los Angeles", "CA", "90012"), ("Chicago", "IL", "60601"), ("Houston", "TX", "77002"),
             ("Phoenix", "AZ", "85004"), ("Philadelphia", "PA", "19103"), ("San Antonio", "TX", "78205"), ("San Diego", "CA", "92101"),
             ("Dallas", "TX", "75201"), ("San Jose", "CA", "95113"), ("Austin", "TX", "78701"), ("Jacksonville", "FL", "32202"),
             ("Columbus", "OH", "43215"), ("Charlotte", "NC", "28202"), ("Indianapolis", "IN", "46204"), ("San Francisco", "CA", "94103"),
             ("Seattle", "WA", "98101"), ("Denver", "CO", "80202"), ("Boston", "MA", "02108"), ("Nashville", "TN", "37203"),
             ("Detroit", "MI", "48226"), ("Portland", "OR", "97204"), ("Las Vegas", "NV", "89101"), ("Memphis", "TN", "38103"),
             ("Louisville", "KY", "40202"), ("Baltimore", "MD", "21202"), ("Milwaukee", "WI", "53202"), ("Albuquerque", "NM", "87102"),
             ("Tucson", "AZ", "85701"), ("Fresno", "CA", "93721"), ("Sacramento", "CA", "95814"), ("Atlanta", "GA", "30303"),
             ("Omaha", "NE", "68102"), ("Raleigh", "NC", "27601"), ("Miami", "FL", "33130"), ("Oakland", "CA", "94612"),
             ("Minneapolis", "MN", "55401"), ("Tulsa", "OK", "74103"), ("Cleveland", "OH", "44113"), ("Tampa", "FL", "33602"),
             ("Pittsburgh", "PA", "15222"), ("Cincinnati", "OH", "45202"), ("St. Louis", "MO", "63101"), ("Orlando", "FL", "32801"),
             ("Buffalo", "NY", "14202"), ("Richmond", "VA", "23219"), ("Salt Lake City", "UT", "84101"), ("Hartford", "CT", "06103"),
             ("Providence", "RI", "02903"), ("Newark", "NJ", "07102"), ("Madison", "WI", "53703"), ("Boise", "ID", "83702"),
             ("Spokane", "WA", "99201"), ("Des Moines", "IA", "50309"), ("Savannah", "GA", "31401"), ("Charleston", "SC", "29401"),
             ("Burlington", "VT", "05401"), ("Portland", "ME", "04101"), ("Anchorage", "AK", "99501"), ("Honolulu", "HI", "96813")]
UK_TOWNS = [("London", "Greater London", "SW1A 1AA"), ("Manchester", "Greater Manchester", "M1 1AE"), ("Birmingham", "West Midlands", "B1 1AA"),
            ("Leeds", "West Yorkshire", "LS1 1UR"), ("Glasgow", "Glasgow City", "G1 1XQ"), ("Liverpool", "Merseyside", "L1 8JQ"),
            ("Bristol", "Bristol", "BS1 4DJ"), ("Sheffield", "South Yorkshire", "S1 2HE"), ("Edinburgh", "City of Edinburgh", "EH1 1YZ"),
            ("Cardiff", "Cardiff", "CF10 1EP"), ("Leicester", "Leicestershire", "LE1 5WW"), ("Coventry", "West Midlands", "CV1 5FB"),
            ("Bradford", "West Yorkshire", "BD1 1HY"), ("Belfast", "County Antrim", "BT1 5GS"), ("Nottingham", "Nottinghamshire", "NG1 5FS"),
            ("Newcastle upon Tyne", "Tyne and Wear", "NE1 7RU"), ("Southampton", "Hampshire", "SO14 7DU"), ("Brighton", "East Sussex", "BN1 1UG"),
            ("Plymouth", "Devon", "PL1 2AA"), ("Reading", "Berkshire", "RG1 2LU"), ("Derby", "Derbyshire", "DE1 2FS"),
            ("Oxford", "Oxfordshire", "OX1 1BX"), ("Cambridge", "Cambridgeshire", "CB2 1TN"), ("York", "North Yorkshire", "YO1 7HH"),
            ("Bath", "Somerset", "BA1 1LZ"), ("Exeter", "Devon", "EX1 1GA"), ("Norwich", "Norfolk", "NR2 1NH"), ("Swansea", "Swansea", "SA1 3SN"),
            ("Aberdeen", "Aberdeen City", "AB10 1AB"), ("Dundee", "Dundee City", "DD1 1DB"), ("Inverness", "Highland", "IV1 1JN"),
            ("Canterbury", "Kent", "CT1 2EH"), ("Chester", "Cheshire", "CH1 2HJ"), ("Lincoln", "Lincolnshire", "LN1 1YL"),
            ("Ipswich", "Suffolk", "IP1 1BX"), ("Luton", "Bedfordshire", "LU1 2NB"), ("Milton Keynes", "Buckinghamshire", "MK9 2AF"),
            ("Harrogate", "North Yorkshire", "HG1 1AA"), ("Durham", "County Durham", "DH1 3NJ"), ("Salisbury", "Wiltshire", "SP1 1EZ")]
US_STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
             "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
             "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
             "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
             "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
             "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
             "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
             "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"}

STREET_SUFFIXES = """Street St Avenue Ave Road Rd Lane Ln Drive Dr Boulevard Blvd Court Ct Place Pl Way Terrace Ter Close Crescent
Cres Gardens Gdns Grove Square Sq Parkway Pkwy Highway Hwy Circle Cir Trail Trl Mews Row Hill Walk View Park Rise Green
Parade Pde Broadway Alley Path Pike Loop Run Point Pt Ridge Square Wharf Quay Embankment Esplanade""".split()

ALIAS_FIRST_M = """Ambrose Barnaby Cormac Dorian Emrys Fergus Gideon Hollis Ignatius Jethro Lachlan Marlow Niall Orson Percival
Quentin Rollo Thaddeus Ulric Wendell Alaric Bertram Cassius Darius Everett Fenwick Garrick Horatio Ishmael Leopold Montague
Nathaniel Octavius Peregrine Roderick Sebastian Tristan Vaughan Wilfred Zebedee Anselm Benedict Clement Desmond Edmund
Florian Godfrey Humphrey Jolyon Lysander""".split()
ALIAS_FIRST_F = """Araminta Beatrix Cordelia Delphine Esmeralda Fenella Georgiana Henrietta Imelda Juniper Lavinia Marigold Ottoline
Perpetua Rosalind Seraphina Tamsin Ursula Verity Winifred Arabella Clementine Drusilla Eugenie Flavia Genevieve Hermione
Isadora Jemima Lucasta Magnolia Octavia Philippa Romilly Saskia Theodora Wilhelmina Anneliese Bryony Coralie Dulcie
Elspeth Felicity Gwendolyn Honora Isolde Lettice Marguerite""".split()
ALIAS_SURNAMES = """Ashcombe Blackwood Cartwright Dunmore Ellingham Fairweather Glanville Hargreaves Ingleby Kingsford Lockwood Marchbank
Northcott Ormsby Pemberton Radcliffe Sandringham Thistlewood Underhill Wexford Abernethy Brackenbury Calloway Delacourt
Everingham Farnsworth Greenhalgh Hatherley Iverson Kettleborough Langridge Mortimer Netherfield Oakenshaw Prendergast
Quarrington Rothwell Stanhope Tillingham Upshaw Vandermeer Whitcombe Yardley Ainsworth Bickerstaff Colquhoun Darlington
Edgerton Fothergill Grisewood Holloway Isherwood Jessop Kilbride Lindqvist Merriweather Nettleton Ollerton Pettigrew
Ravensworth Sedgwick Trevelyan Wadsworth""".split()
ALIAS_STREETS = """Juniper Birchwood Hawthorn Larkspur Briarwood Foxglove Primrose Kestrel Linden Whitethorn Sycamore Bramble
Heatherfield Rowanberry Elderflower Mulberry Chestnut Ashgrove Willowbank Thistledown Meadowsweet Holloway Ferncliff
Silverbirch Kingfisher Wrenfield Ivybridge Copperbeech Oakhurst Harebell""".split()
ALIAS_ORGS = """Northwind Holdings|Bluegate Services|Harbourline Consulting|Ridgeway Partners|Silverline Logistics|Oakfield Systems""".split("|")

# Ordinary English words that may be capitalised (sentence start, headings): never names on their own.
COMMON_WORDS = {norm(w) for w in """The This That These Those There Here Then When Where What Which Who Whom Whose Why How
And But Or Nor For Yet So If Although Because Since Unless While After Before During Following Pursuant Re Dear Sir
Madam Sincerely Regards Yours Faithfully Kind Best Thanks Thank Please Note Notice Subject Date From To Cc Bcc Sent
Attached Attachment Enclosed Enclosure Page Total Amount Balance Payment Payments Account Statement Policy Claim Case
Number No Reference Ref Name Address Phone Telephone Mobile Email Fax Patient Hospital Clinic Doctor Nurse Ward
Department Discharge Summary Diagnosis Treatment Medication Medications Allergies History Plan Assessment Findings
Agreement Contract Lease Tenancy Landlord Tenant Employer Employee Section Clause Article Schedule Appendix Exhibit
Court County State District Superior Supreme Federal City Council Police Officer Report Incident Witness Statement
Insurance Insured Vehicle Driver Registration Make Model Year Bank Branch Sort Code Routing Card Credit Debit Visa
Mastercard Amex Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July
August September October November December Mr Mrs Ms Miss Mx Dr Prof Professor Hon Rev Reverend Judge Justice Esq
Ltd Limited LLC Inc Corp Corporation Company Co PLC LLP Trust Group Holdings Services NHS HMRC IRS SSA DMV FBI USA UK
United States Kingdom America American British English Street Road Avenue Lane Drive Boulevard Suite Apt Apartment
Flat Unit Floor Building House Office Room Box PO ZIP Postcode Tax Income Gross Net Pay Pension National Social Security
Medicare Medicaid Health Care Medical Record Insurance Member Group Plan Provider Primary Emergency Contact Next Kin
Signature Signed Witnessed Approved Received Issued Effective Expires Expiry Valid Total Subtotal Due Overdue Final
Notice Demand Letter Complaint Plaintiff Defendant Claimant Respondent Petitioner Appellant Counsel Attorney Solicitor
Barrister Firm Partner Associate Paralegal Clerk Secretary Manager Director President Chair Chairman Treasurer Board
Minutes Meeting Present Absent Apologies Agenda Item Motion Resolved Action Owner Status Open Closed Pending Yes No
All Any Each Every Some Many Much More Most Other Another Such Only Also Just Very Our Your Their His Her Its My We
You They He She It I Me Us Them Him Not None One Two Three First Second Third Last Next New Old Good Great High Low
North South East West Northern Southern Eastern Western Central Upper Lower Greater Royal Saint St Mount Lake Port
Fort Bay Beach Valley River Spring Springs Falls Heights Village Town Borough Parish Shire Main Market Church Station
Hospital School University College Academy Institute Center Centre Department Division Unit Team Office""".split()}


def nomi_primi() -> set:
    return {norm(x) for x in FIRST_M + FIRST_F}


def cognomi() -> set:
    return {norm(x) for x in SURNAMES}


def genere(nome: str) -> str | None:
    n = norm(nome)
    m = n in {norm(x) for x in FIRST_M}
    f = n in {norm(x) for x in FIRST_F}
    if m and not f:
        return "M"
    if f and not m:
        return "F"
    return None

# Titles are never names on their own («Mrs» after «cc:» must not become a surname).
TITOLI_EN = {norm(w) for w in "Mr Mrs Ms Miss Mx Dr Prof Sir Dame Lord Lady Rev Hon Judge Justice Sgt Det Capt Lt Atty Messrs".split()}
COMMON_WORDS |= TITOLI_EN

# Words found in organisation names, headings and signature blocks: never a person on their own.
COMMON_WORDS |= {norm(w) for w in """Realty Property Properties Personnel Facilities Facility Team Teams Act Acts Housing Fees Fee
Bakery Basin Management Services Service Department Dept Office Offices Group Holdings Bank Banking Insurance Hospital Clinic
Center Centre University College School Council Court Courts County Borough Trust Foundation Association Society Company
Partners Partnership Solicitors Lawyers Law Legal Associates Consulting Logistics Systems Solutions Agency Authority Board
Committee Commission Union Credit Financial Finance Mortgage Lending Loans Capital Investments Securities Federal National
State Regional Municipal Community Health Medical Care Pharmacy Dental Veterinary Animal Pet Pets Motors Auto Autos Garage
Repairs Plumbing Electric Electrical Energy Water Gas Utilities Telecom Mobile Broadband Hotel Restaurant Cafe Bar Pub Store
Stores Shop Market Supermarket Grocery Bakery Deli Salon Studio Gallery Theatre Theater Cinema Church Parish Mosque Temple
Library Museum Gardens Estate Estates Residence Residences Apartments Condominium Homeowners Tenants Landlords Lettings
Acknowledged Acknowledgement Received Signed Signature Witness Witnessed Approved Reviewed Prepared Attachment Attachments
Enclosure Enclosures Tel Telephone Phone Fax Email E-mail Mobile Cell Web Website Ref Reference Subject Re Fwd Fw Date Time
Total Balance Amount Payment Payments Deposit Deposits Withdrawal Transfer Transfers Statement Summary Notice Letter Report
Pacific Atlantic Northern Southern Eastern Western Central Coastal Valley Ridge Harbor Harbour Bay Lake River Mountain
Lucky Golden Silver Royal Crown Premier Prime Elite Global International Universal United American British English Scottish
Welsh Irish Italian European""".split()}


# ------------------------------------------------------------------ larger dictionaries (sosia/dizionari)
def _righe(nome: str) -> list[str]:
    from pathlib import Path
    p = Path(__file__).with_name("dizionari") / nome
    if not p.exists():
        return []
    return [r.strip() for r in p.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]


LUOGHI_US = [tuple(r.split(";", 1)) for r in _righe("luoghi_us.txt") if ";" in r]
LUOGHI_UK = [tuple(r.split(";", 1)) for r in _righe("luoghi_uk.txt") if ";" in r]
LUOGHI_EN = {norm(c) for c, _ in LUOGHI_US + LUOGHI_UK}
AMBIGUI_LUOGHI_EN = {norm(x) for x in _righe("ambigui_en.txt")}
# 0.6.0: elenchi ufficiali (OS Open Names, ONS, Census 2010), solo con contesto e fuori dalle parole comuni del prefiltro
LUOGHI_GB_UFF = {norm(r.split(";")[0]) for r in _righe("osn_luoghi_gb.txt")} - LUOGHI_EN
VIE_GB_UFF = {norm(r) for r in _righe("osn_vie_gb.txt")}
_ONS = [r.split(";") for r in _righe("ons_nomi_uk.txt") if ";" in r]
NOMI_UFF_M = {norm(n) for n, g in _ONS if g in ("M", "U")}
NOMI_UFF_F = {norm(n) for n, g in _ONS if g in ("F", "U")}
COGNOMI_UFF = {norm(r) for r in _righe("census_cognomi_us.txt")}
# fuori le parole comuni (elenco grezzo, prima di togliere nomi e cognomi), i luoghi e gli stati: «Park», «Summit»,
# «Florida», «Ford» sono cognomi veri, ma in un testo sono quasi sempre altro
_GREZZE = {norm(r) for r in _righe("parole_comuni_en.txt") + _righe("parole_comuni_it.txt")}
_LUOGHI_TUTTI = LUOGHI_EN | LUOGHI_GB_UFF | {norm(x) for x in US_STATES.values()} | {norm(x) for x in US_STATES}
COGNOMI_UFF -= _GREZZE | _LUOGHI_TUTTI | COMMON_WORDS
NOMI_UFF_M -= _GREZZE | _LUOGHI_TUTTI | COMMON_WORDS
NOMI_UFF_F -= _GREZZE | _LUOGHI_TUTTI | COMMON_WORDS
SURNAME_WORDS |= {norm(x) for x in _righe("ambigui_nomi.txt")}


def nomi_primi() -> set:  # noqa: F811 — con i dizionari estesi
    from .dati import NOMI_EXTRA_F, NOMI_EXTRA_M
    return {norm(x) for x in FIRST_M + FIRST_F} | NOMI_EXTRA_M | NOMI_EXTRA_F


def cognomi() -> set:  # noqa: F811
    from .dati import COGNOMI_EXTRA
    return {norm(x) for x in SURNAMES} | COGNOMI_EXTRA

# Roles and generic nouns that the model sometimes tags as persons («Tenant», «Patient», «GP»).
COMMON_WORDS |= {norm(w) for w in """Tenant Tenants Landlord Landlords Patient Patients GP MD DO RN NP PA Deputy Sergeant Officer
Detective Constable Inspector Captain Lieutenant Judge Justice Magistrate Clerk Registrar Claimant Plaintiff Defendant
Respondent Appellant Applicant Employee Employer Manager Supervisor Director Chairman Chairperson Chair Secretary Treasurer
President Vice Member Members Resident Residents Owner Owners Buyer Seller Borrower Lender Guarantor Insured Insurer Policyholder
Beneficiary Executor Trustee Witness Doctor Nurse Consultant Surgeon Physician Therapist Counsellor Counselor Solicitor Barrister
Attorney Counsel Paralegal Agent Broker Adjuster Assessor Appraiser Human Resources HR Payroll Tax Taxes Deed Deeds Title Titles
Lease Tenancy Agreement Contract Claim Claims Policy Account Customer Client Applicant Student Parent Guardian You Your Sir Madam
Dear Regards Sincerely Thanks Thank Kind Best Warm""".split()}
COMMON_WORDS |= {norm(w) for w in """Father Mother Renter Renters Cedente Cessionario Cessionaria Nursery Jr Sr Probate Landscaping Home
Admissions Admission Loan HOA VIN Bill Injury Occupational Temporary Youth Principal International Agreed Send Desert Creek""".split()}
