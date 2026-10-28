"""Dizionari locali: nomi, cognomi, comuni, vie, parole che non sono nomi.

Tutto è scritto a mano e resta locale: nessun download. Le liste servono a due cose diverse:
- riconoscere (nomi e cognomi frequenti, titoli, parole maiuscole che non sono nomi);
- inventare (alias realistici, scelti fra parole che NON sono anche parole comuni italiane,
  così il ripristino non scambia «bianchi» aggettivo per il cognome finto «Bianchi»).
"""
from __future__ import annotations

import functools
import unicodedata


@functools.lru_cache(maxsize=200000)
def norm(s: str) -> str:
    """Minuscolo, senza accenti, apostrofo tipografico normalizzato."""
    if s.isascii():  # caso più frequente: niente accenti da togliere (avvio rapido con gli elenchi ufficiali)
        return s.lower()
    s = unicodedata.normalize("NFD", s.replace("’", "'"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


NOMI_M = """Mario Giuseppe Giovanni Antonio Francesco Luigi Angelo Vincenzo Pietro Salvatore Carlo Domenico
Bruno Paolo Michele Giorgio Aldo Sergio Luciano Roberto Alessandro Andrea Marco Luca Matteo Lorenzo Davide
Simone Federico Riccardo Gabriele Stefano Massimo Fabio Claudio Maurizio Enrico Alberto Daniele Emanuele Nicola
Raffaele Gianni Gianluca Gianfranco Giancarlo Filippo Tommaso Leonardo Edoardo Giacomo Cristian Christian Diego
Emilio Ettore Ferdinando Fernando Gaetano Guido Ivan Jacopo Lucio Manuel Mattia Mauro Nicolò Niccolò Ottavio
Pasquale Renato Rocco Samuele Silvio Ugo Umberto Valerio Walter Carmine Cosimo Alfredo Arturo Dario Elia Enzo
Flavio Giulio Ignazio Marcello Nunzio Orazio Piero Rino Tiziano Vittorio Ernesto Gino Lino Alessio Fausto
Gennaro Corrado Benito Elio Ezio Fulvio Giacinto Igor Livio Loris Massimiliano Nazzareno Osvaldo Primo Romano
Rodolfo Silvano Tullio Valentino Vito Agostino Alfonso Amedeo Armando Attilio Augusto Baldassarre Biagio Calogero
Ciro Costantino Damiano Donato Egidio Eugenio Fabrizio Franco Gerardo Germano Gianpaolo Gianmarco Gilberto
Girolamo Graziano Gregorio Leopoldo Luigino Marcello Mariano Mirko Moreno Natale Nello Oreste Pierluigi Pierpaolo
Raimondo Remo Renzo Riccardo Rolando Rosario Ruggero Sandro Saverio Sebastiano Severino Teodoro Tiberio Tommaso
Vladimiro Zeno Adriano Aurelio Cesare Cristiano Denis Emiliano Ermanno Federico Gabriel Kevin Michael Nicholas
Pietro Raoul Thomas Alex Ivano Luigi Erminio Giordano Ilario Manlio Settimio Spartaco Tarcisio Ubaldo""".split()

NOMI_F = """Maria Anna Giuseppina Rosa Angela Giovanna Teresa Lucia Carmela Caterina Francesca Antonietta Carla
Elena Concetta Rita Margherita Franca Paola Laura Giulia Sofia Aurora Alice Ginevra Emma Giorgia Greta Beatrice
Martina Chiara Sara Valentina Alessia Federica Silvia Roberta Elisa Monica Cristina Barbara Simona Daniela
Patrizia Claudia Manuela Stefania Raffaella Michela Ilaria Eleonora Camilla Marta Irene Noemi Arianna Rebecca
Ludovica Vittoria Nicoletta Lorena Lorenza Luisa Marina Mirella Nadia Ornella Orietta Pamela Rachele Renata
Rossella Sabrina Sandra Serena Sonia Tiziana Valeria Veronica Viviana Wanda Adele Agnese Alba Alessandra Alda
Amalia Antonella Assunta Benedetta Bianca Bruna Carlotta Cecilia Clara Costanza Debora Diana Donatella Elisabetta
Emanuela Enrica Erica Ester Fabiana Fabrizia Filomena Flavia Gabriella Gemma Gianna Gina Gloria Grazia Graziella
Ida Immacolata Ines Iolanda Isabella Jessica Lara Letizia Liliana Lina Livia Loredana Lucrezia Maddalena Mara
Marcella Margot Mariangela Marisa Matilde Melissa Miriam Morena Natalia Nina Olga Paolina Piera Pina Raffaela
Regina Rina Romina Sabina Samanta Silvana Simonetta Stella Susanna Tamara Teodora Ursula Vanessa Vera Viola Virginia
Ylenia Zaira Agata Annalisa Annamaria Carolina Elvira Emilia Erika Eva Fiorella Giada Giuliana Irma Katia Lea
Lisa Maura Michelle Nives Norma Ottavia Rosalba Rosanna Rosaria Sveva Teresa Vincenza Licia Gaia Asia Nicole
Chantal Alessandra Lucilla Mariella Mariagrazia Mariarosaria Annunziata Addolorata Carmen""".split()

# Nomi diffusi fra i residenti di origine straniera e diminutivi frequenti (riconoscimento, non alias).
NOMI_M += """Mohamed Mohammed Ahmed Ali Omar Youssef Hassan Karim Rachid Abdel Ion Vasile Andrei Mihai Florin Bogdan
Adrian Marius Dmitri Sergei Oleksandr Taras Wojciech Piotr Tomasz Krzysztof Pawel Arben Ardit Besnik Wei Jun Hao
Raj Amit Singh Jose Juan Carlos Luis Pedro Miguel Kevin Daniel David Samuel Patrick Peppe Beppe Pino Gigi Nino
Gian Pier Piergiorgio Gianpiero Giampaolo Giammarco Pierfrancesco Tonino Totò Toto Ciccio Pippo Teo Gabri Lollo""".split()
NOMI_F += """Fatima Aicha Khadija Amina Samira Leila Ioana Mihaela Andreea Irina Natalia Svetlana Oksana Tetiana
Yuliya Iuliia Olena Halyna Katarzyna Agnieszka Malgorzata Ewa Ivana Jelena Ana Mei Xin Priya Pina Gina Titti
Cettina Mimma Ninni Sere Vale Fra Giò Bea Ele Fede Ale Mari""".split()

SIGLE_PROVINCE = set("""AG AL AN AO AP AQ AR AT AV BA BG BI BL BN BO BR BS BT BZ CA CB CE CH CL CN CO CR CS CT CZ EN FC FE
FG FI FM FR GE GO GR IM IS KR LC LE LI LO LT LU MB MC ME MI MN MO MS MT NA NO NU OR PA PC PD PE PG PI PN PO PR PT
PU PV PZ RA RC RE RG RI RM RN RO SA SI SO SP SR SS SU SV TA TE TN TO TP TR TS TV UD VA VB VC VE VI VR VT VV""".split())

# Nomi che in Italia sono di entrambi i generi o maschili ma finiscono in -a (Andrea, Luca, Nicola, Mattia, Elia).
AMBIGUI_GENERE = {"andrea": "M", "luca": "M", "nicola": "M", "mattia": "M", "elia": "M", "enea": "M", "battista": "M",
                  "celeste": "F", "felice": "M", "fortunata": "F", "rosario": "M", "maria": "F", "gabriel": "M"}

COGNOMI = """Rossi Russo Ferrari Esposito Bianchi Romano Colombo Ricci Marino Greco Bruno Gallo Conti De Luca Mancini
Costa Giordano Rizzo Lombardi Moretti Barbieri Fontana Santoro Mariani Rinaldi Caruso Ferrara Galli Martini Leone
Longo Gentile Martinelli Vitale Lombardo Serra Coppola De Santis D'Angelo Marchetti Parisi Villa Conte Ferraro
Ferri Fabbri Bianco Marini Grasso Valentini Messina Sala De Angelis Gatti Pellegrini Palumbo Sanna Farina Rizzi
Monti Cattaneo Morelli Amato Silvestri Mazza Testa Grassi Pellegrino Carbone Giuliani Benedetti Barone Rossetti
Caputo Montanari Guerra Palmieri Bernardi Martino Fiore De Rosa Ferretti Bellini Basile Riva Donati Piras Vitali
Battaglia Sartori Neri Costantini Milani Pagano Ruggiero Sorrentino D'Amico Orlando Damico Negri Gentili Bassi
Fumagalli Brambilla Galimberti Pozzi Colombi Ferrario Cattani Zanetti Bortolotti Zanella Benetti Toffoli Zampieri
Bonetti Bonomi Bertolini Bertoni Caprioli Cavalli Cocco Corsi Cristiani De Marco Di Stefano Di Pietro Esposti Fabbro
Fadda Fiorentino Fois Frau Gargiulo Gatto Ghidini Guidi Iannone Lanza Lazzari Leoni Lupo Maggi Manca Marras Melis
Meloni Merlo Mura Nardi Orrù Pace Pagani Pirisi Porcu Puddu Rota Ruggeri Russo Salvi Santini Sardo Sartori Scotti
Serafini Sergi Spinelli Tedesco Tosi Valente Vacca Zanotti Zito Agostini Albanese Alberti Aloisi Antonelli Arena
Bellucci Bernardini Bertolotti Bevilacqua Bianconi Bonfanti Borghi Brunetti Buzzi Calabrese Capasso Carli Carrara
Casale Castagna Cerri Chiesa Cirillo Colonna Corradi Cozzi D'Alessandro Del Prete Della Valle Dell'Orto De Simone
Di Giacomo Di Lorenzo Fabbrini Falco Ferrante Fiorini Gallo Giannini Grillo Guarino Lattanzi Lodi Lorenzi Lucchesi
Mancuso Marchi Mazzola Miceli Mele Moro Mosca Musso Nicoletti Olivieri Orsini Pastore Pepe Perrone Petrucci Piccolo
Pini Poli Pugliese Quaranta Rampini Riccardi Rocca Romeo Rosati Sacco Salerno Sanfilippo Santangelo Sarti Savino
Scarpa Schiavone Silvestro Sorce Sposito Tagliaferri Tarantino Toscano Tripodi Valenti Vecchi Venturi Viola Zanoni""".split()
# I cognomi composti («De Luca», «D'Angelo») sono spezzati dallo split: li ricompone il riconoscitore con le particelle.

# Alias: parole che in italiano NON sono anche parole comuni (niente «Rossi», «Conti», «Gatti», «Ferri»).
ALIAS_COGNOMI = """Galimberti Brambilla Fumagalli Zanetti Bortolotti Zanella Benetti Toffoli Zampieri Bonetti Bonomi
Bertolini Caprioli Cattani Ghidini Iannone Lazzari Marras Melis Pirisi Porcu Puddu Scotti Serafini Zanotti Agostini
Aloisi Antonelli Bellucci Bernardini Bertolotti Bevilacqua Bianconi Bonfanti Brunetti Buzzi Capasso Carrara Cerri
Cirillo Corradi Cozzi Fabbrini Fiorini Giannini Guarino Lattanzi Lorenzi Lucchesi Mancuso Mazzola Miceli Nicoletti
Olivieri Orsini Perrone Petrucci Quaranta Rampini Riccardi Rosati Sanfilippo Santangelo Savino Schiavone Tagliaferri
Tarantino Tripodi Venturi Zanoni Mastrangelo Pagliarini Righetti Spadoni Tamburini Vannucci Zucchelli Ballarin
Boscolo Carminati Castellani Crivelli Dalmasso Ferrandi Gualtieri Lanfranchi Losurdo Maestrini Mantovani Marcolin
Morandini Nardelli Ottolini Pasquali Pavan Pedrazzini Piovesan Prandini Quadrelli Rigamonti Scaglia Sgarbossa
Tognon Trevisan Vezzoli Zaccaria Zambon Bergamaschi Bortolin Cappelletti Ceccarelli Donadoni Facchini Gasparini
Lombardini Marangoni Michelini Pierantoni Rebecchi Sacchetti Stefanelli Tonelli Verdolini Zanardi""".split()

ALIAS_NOMI_M = """Luca Matteo Lorenzo Davide Simone Federico Riccardo Gabriele Stefano Massimo Fabio Claudio Maurizio
Enrico Alberto Daniele Emanuele Raffaele Gianluca Filippo Tommaso Leonardo Edoardo Giacomo Diego Emilio Ettore
Gaetano Guido Jacopo Mattia Mauro Ottavio Pasquale Renato Samuele Valerio Cosimo Alfredo Arturo Dario Flavio Giulio
Ignazio Marcello Orazio Tiziano Vittorio Ernesto Alessio Fausto Gennaro Corrado Fulvio Livio Osvaldo Rodolfo Silvano
Tullio Agostino Alfonso Amedeo Armando Attilio Augusto Biagio Ciro Damiano Donato Egidio Eugenio Fabrizio Gerardo
Gilberto Graziano Gregorio Leopoldo Mariano Mirko Oreste Pierluigi Raimondo Remo Renzo Rolando Ruggero Sandro
Saverio Sebastiano Teodoro Adriano Aurelio Cristiano Emiliano Ermanno Ivano Ilario Manlio Ubaldo""".split()

ALIAS_NOMI_F = """Giulia Sofia Aurora Alice Ginevra Emma Giorgia Greta Beatrice Martina Chiara Sara Valentina Alessia
Federica Silvia Roberta Elisa Monica Cristina Barbara Simona Daniela Patrizia Claudia Manuela Stefania Raffaella
Michela Ilaria Eleonora Camilla Marta Irene Noemi Arianna Rebecca Ludovica Nicoletta Lorena Luisa Marina Mirella
Nadia Ornella Pamela Rachele Renata Rossella Sabrina Sandra Sonia Tiziana Valeria Veronica Viviana Adele Agnese
Alessandra Amalia Antonella Benedetta Carlotta Cecilia Clara Costanza Debora Donatella Elisabetta Emanuela Enrica
Erica Ester Fabiana Flavia Gabriella Gemma Graziella Ida Ines Iolanda Isabella Lara Letizia Liliana Livia Loredana
Lucrezia Maddalena Marcella Mariangela Marisa Matilde Melissa Miriam Natalia Olga Paolina Romina Sabina Silvana
Simonetta Susanna Tamara Vanessa Virginia Annalisa Carolina Elvira Emilia Fiorella Giada Giuliana Katia Ottavia""".split()

# Nomi di battesimo che sono anche parole comuni: servono indizi in più per riconoscerli.
NOMI_PAROLA = {norm(x) for x in """Rosa Bianca Serena Speranza Fortunato Felice Celeste Viola Gioia Stella Vera Grazia
Pace Sole Fiore Marino Franco Leone Santo Angelo Fedele Benvenuto Valente Diamante Amore Primo Natale Regina Gemma
Margherita Aurora Alba Romano Domenico Lino Moreno Assunta Immacolata Concetta Carmela Pia Nina Eva Lea""".split()}

# Cognomi che sono anche parole comuni o città.
COGNOMI_PAROLA = {norm(x) for x in """Rossi Bianchi Neri Russo Bruno Gallo Conti Costa Fontana Villa Riva Monti Leone
Marino Greco Galli Testa Grasso Rocca Sala Pellegrini Fabbri Gatti Porta Corti Messina Ferrara Farina Gentile
Serra Pagano Mazza Vitale Fiore Carbone Ricci Bassi Piazza Guerra Martino Marchi Castelli Valle Pace Moro Mosca
Pepe Piccolo Sacco Salerno Lupo Merlo Ferri Tedesco Toscano Pugliese Calabrese Sardo Albanese Romano Colombo
Bianco Longo Amato Barone Negri Vecchi Viola Lodi Arena Chiesa Colonna Falco Grillo Scarpa Musso Mele Poli Pini
Quaranta Lanza Orlando Basile Fiorentino Rota Conte Santi Rosa Mancini Romeo""".split()}

# Persone celebri: nei nomi di vie, scuole e ospedali non vanno trattate come persone del documento.
CELEBRI = {norm(x) for x in """Garibaldi Mazzini Cavour Verdi Puccini Rossini Volta Marconi Galilei Galileo Manzoni
Leopardi Carducci Pascoli D'Annunzio Dante Alighieri Petrarca Boccaccio Machiavelli Colombo Vespucci Fermi Montessori
Matteotti Gramsci Mattei Moro Berlinguer Pertini Einaudi Gobetti Battisti Oberdan Sauro Diaz Cadorna Vittorio Emanuele
Umberto Margherita Savoia Medici Michelangelo Raffaello Leonardo Caravaggio Bernini Giotto Vivaldi Bellini Donizetti
Toscanini Pirandello Verga Deledda Montale Ungaretti Quasimodo Pavese Calvino Fellini Falcone Borsellino Matteotti
Kennedy Gandhi Mandela Einstein Newton Pasteur Fleming Sabin Cotugno Gemelli Niguarda Rizzoli Cardarelli Pascale
Sant'Orsola Careggi Molinette Galliera Policlinico""".split()}

# Parole maiuscole che non sono mai nomi di persona (mesi, giorni, istituzioni, intestazioni frequenti).
NON_NOMI = {norm(x) for x in """Gennaio Febbraio Marzo Aprile Maggio Giugno Luglio Agosto Settembre Ottobre Novembre
Dicembre Lunedì Martedì Mercoledì Giovedì Venerdì Sabato Domenica Oggetto Spett Spettabile Egregio Egregia Gentile
Gentilissimo Gentilissima Caro Cara Tribunale Corte Procura Giudice Avvocato Avvocata Avv Dott Dottor Dottore Dottoressa
Sig Signor Signora Signore Sigra Prof Professore Professoressa Ing Ingegnere Geom Rag Arch Notaio Studio Legale
Società Azienda Comune Regione Provincia Repubblica Italia Italiana Stato Ministero Agenzia Entrate INPS INAIL ASL
ASST ATS Ospedale Reparto Clinica Medicina Chirurgia Cardiologia Ortopedia Pediatria Ginecologia Neurologia Pronto
Soccorso Diagnosi Anamnesi Terapia Paziente Cartella Ricovero Dimissione Referto Esame Allegato Allegati Pagina
Firma Firmato Data Luogo Nome Cognome Codice Fiscale Partita IVA Iban Indirizzo Telefono Email Cellulare Via Viale
Piazza Corso Largo Vicolo Contratto Articolo Art Premesso Considerato Visto Tutto Ciò Premesse Parte Parti
Committente Appaltatore Locatore Conduttore Lavoratore Datore Lavoro Dipendente Cliente Fornitore Banca Conto Euro
Totale Importo Netto Lordo Busta Paga Cedolino Mese Anno Verbale Riunione Presenti Assenti Ordine Giorno Punto
Cronologia Evento Eventi Note Nota Distinti Saluti Cordiali Grazie Buongiorno Buonasera Salve Ciao Il La Lo Le Gli
I Un Una Uno Del Della Dello Dei Degli Delle Nel Nella In Con Per Su Da Di A E O Ma Se Che Non Si Ci Questo Questa
Questi Queste Quello Quella Sono Siamo Hanno Abbiamo Ho Ha Al Alla Ai Alle Dal Dalla Sul Sulla Tra Fra Come Dove
Quando Perché Anche Ancora Già Poi Dopo Prima Entro Oltre Presso Pec Fax Tel Cell Mail Mob Ufficio Sede Legale
Operativa Responsabile Direttore Direttrice Presidente Segretario Segretaria Amministratore Unico Delegato Procuratore
Consulente Tecnico Medico Infermiere Primario Specialista Curante Dirigente Ricorrente Resistente Convenuto Attore
Imputato Persona Offesa Testimone Teste Udienza Sentenza Decreto Ordinanza Ricorso Atto Citazione Diffida Messa Mora
Raccomandata Lettera Oggetto Rif Riferimento Protocollo Prot Pratica Fascicolo Numero Sinistro Polizza Assicurazione
Spa Srl Snc Sas Srls Onlus Asd Aps Coop Cooperativa Fondazione Associazione Gruppo Holding Consorzio Ente Istituto
Università Scuola Liceo Facoltà Dipartimento Laboratorio Centro Servizi Sanitari Nazionale Regionale Provinciale
Comunale Locale Unità Sanitaria Nord Sud Est Ovest Centro Alta Bassa Santo Santa San Sant Beato Madonna Maria
Gesù Cristo Dio Natale Pasqua Ferragosto Capodanno Epifania Commercialista Revisore Contabile Geometra Ingegnere
Architetto Perito Infermiere Infermiera Ragioniere Ragioniera Medico Chirurgo Farmacista Dentista Psicologo Psicologa
Mamma Papà Papa Nonno Nonna Zio Zia Cugino Cugina Fratello Sorella Figlio Figlia Marito Moglie Suocera Suocero
Amministrazione Condominio Condomino Condomini Scala Interno Assemblea Agenzia Immobiliare Ufficio Sezione Foro
Operatore Operatrice Agente Utente Cliente Interlocutore Chiamante Cap Tel Fax Cell Sua Suo Suoi Sue Lei Loro Voi Vostro Vostra Ella Egli Esso Essa Ucraina Romania Polonia Marocco Albania Cina India Francia Germania Spagna Svizzera Europa Ue Inps Inail""".split()}

# Comuni: nome, sigla provincia, CAP principale, codice catastale (Belfiore).
# Tabella ridotta ai capoluoghi più grandi: basta per inventare indirizzi e codici fiscali verosimili.
COMUNI = [
    ("Roma", "RM", "00185", "H501"), ("Milano", "MI", "20121", "F205"), ("Napoli", "NA", "80133", "F839"),
    ("Torino", "TO", "10121", "L219"), ("Palermo", "PA", "90133", "G273"), ("Genova", "GE", "16121", "D969"),
    ("Bologna", "BO", "40121", "A944"), ("Firenze", "FI", "50122", "D612"), ("Bari", "BA", "70121", "A662"),
    ("Catania", "CT", "95121", "C351"), ("Venezia", "VE", "30121", "L736"), ("Verona", "VR", "37121", "L781"),
    ("Messina", "ME", "98122", "F158"), ("Padova", "PD", "35121", "G224"), ("Trieste", "TS", "34121", "L424"),
    ("Brescia", "BS", "25121", "B157"), ("Parma", "PR", "43121", "G337"), ("Taranto", "TA", "74121", "L049"),
    ("Prato", "PO", "59100", "G999"), ("Modena", "MO", "41121", "F257"), ("Reggio Calabria", "RC", "89121", "H224"),
    ("Reggio Emilia", "RE", "42121", "H223"), ("Perugia", "PG", "06121", "G478"), ("Livorno", "LI", "57121", "E625"),
    ("Ravenna", "RA", "48121", "H199"), ("Cagliari", "CA", "09121", "B354"), ("Foggia", "FG", "71121", "D643"),
    ("Rimini", "RN", "47921", "H294"), ("Salerno", "SA", "84121", "H703"), ("Ferrara", "FE", "44121", "D548"),
    ("Sassari", "SS", "07100", "I452"), ("Latina", "LT", "04100", "E472"), ("Monza", "MB", "20900", "F704"),
    ("Siracusa", "SR", "96100", "I754"), ("Pescara", "PE", "65121", "G482"), ("Bergamo", "BG", "24121", "A794"),
    ("Trento", "TN", "38122", "L378"), ("Vicenza", "VI", "36100", "L840"), ("Terni", "TR", "05100", "L117"),
    ("Bolzano", "BZ", "39100", "A952"), ("Novara", "NO", "28100", "F952"), ("Piacenza", "PC", "29121", "G535"),
    ("Ancona", "AN", "60121", "A271"), ("Arezzo", "AR", "52100", "A390"), ("Udine", "UD", "33100", "L483"),
    ("Lecce", "LE", "73100", "E506"), ("Como", "CO", "22100", "C933"), ("Pisa", "PI", "56121", "G702"),
    ("Lucca", "LU", "55100", "E715"), ("Varese", "VA", "21100", "L682"), ("Treviso", "TV", "31100", "L407"),
    ("Caserta", "CE", "81100", "B963"), ("Asti", "AT", "14100", "A479"), ("Pavia", "PV", "27100", "G388"),
    ("Cremona", "CR", "26100", "D150"), ("Viterbo", "VT", "01100", "M082"), ("Benevento", "BN", "82100", "A783"),
    ("Avellino", "AV", "83100", "A509"), ("Potenza", "PZ", "85100", "G942"), ("Matera", "MT", "75100", "F052"),
    ("Catanzaro", "CZ", "88100", "C352"), ("Cosenza", "CS", "87100", "D086"), ("L'Aquila", "AQ", "67100", "A345"),
    ("Campobasso", "CB", "86100", "B519"), ("Aosta", "AO", "11100", "A326"), ("Siena", "SI", "53100", "I726"),
    ("Mantova", "MN", "46100", "E897"), ("Cuneo", "CN", "12100", "D205"), ("Savona", "SV", "17100", "I480"),
    ("Pistoia", "PT", "51100", "G713"), ("Rovigo", "RO", "45100", "H620"), ("Lodi", "LO", "26900", "E648"),
    ("Lecco", "LC", "23900", "E507"), ("Brindisi", "BR", "72100", "B180"), ("Trapani", "TP", "91100", "L331"),
    ("Agrigento", "AG", "92100", "A089"), ("Ragusa", "RG", "97100", "H163"), ("Teramo", "TE", "64100", "L103"),
]

# Comuni usati come alias: si evitano i nomi che sono anche parole o cognomi frequenti (Messina, Ferrara, Lodi…).
ALIAS_COMUNI_ESCLUSI = {"Messina", "Ferrara", "Lodi", "Salerno", "Latina", "Asti", "Como", "Prato", "Lucca", "Siena"}

PREFISSI_STRADA = ["Via", "Viale", "V.le", "Piazza", "P.zza", "P.za", "Piazzale", "Corso", "C.so", "Largo", "Vicolo",
                   "Strada", "Contrada", "C.da", "Località", "Loc.", "Borgo", "Lungomare", "Lungotevere", "Salita",
                   "Traversa", "Rione", "Viuzza", "Calle", "Fondamenta", "Galleria", "Passaggio", "Stradone", "Vico",
                   "Scali", "Scalo", "Calata", "Discesa", "Rampa", "Riva", "Campo", "Vicoletto", "Lungarno", "Circonvallazione",
                   "Lungolago", "Lungofiume", "Piazzetta", "Corte", "Sentiero",
                   # 0.6.0: indirizzi di campagna
                   "Strada vicinale", "Strada comunale", "Strada provinciale", "Strada statale", "Strada poderale",
                   "Strada interpoderale", "Cascina", "Podere", "Masseria", "Borgata", "Casale", "Baita", "Malga"]

ALIAS_VIE = """dei Ciclamini|delle Gardenie|dei Gelsomini|delle Mimose|dei Tulipani|delle Ortensie|dei Glicini|dei Mughetti|
delle Camelie|degli Oleandri|dei Castagni|dei Faggi|degli Ontani|dei Platani|delle Querce|dei Tigli|degli Abeti|
dei Larici|delle Betulle|dei Cipressi|del Bersaglio|della Fornace|del Mulino Vecchio|della Cartiera|delle Filande|
del Gelso|della Pergola|del Frantoio|delle Fonti|del Pozzo|della Cisterna|delle Fornaci|dei Vetrai|dei Tessitori|
dei Cordai|dei Bottai|degli Speziali|dei Fabbri Ferrai|della Lanterna|del Faro|della Bussola|dei Gabbiani|
degli Aironi|delle Rondini|dei Fringuelli|delle Allodole|dei Pettirossi|delle Cicogne|del Lauro|del Rosmarino""".replace("\n", "").split("|")

DOMINI_PUBBLICI = {"gmail.com", "libero.it", "yahoo.it", "yahoo.com", "hotmail.it", "hotmail.com", "outlook.it",
                   "outlook.com", "live.it", "virgilio.it", "tiscali.it", "alice.it", "tin.it", "icloud.com",
                   "me.com", "fastwebnet.it", "email.it", "pec.it", "legalmail.it", "postecert.it", "arubapec.it",
                   "pec.libero.it", "proton.me", "protonmail.com", "inwind.it", "aruba.it", "gmx.com", "msn.com"}

ALIAS_PAROLE_DOMINIO = """studioalfa servizinord consulenzeest tecnoprogetti archimedia lexpartners mediplus
cliniconord ortocentro edilnova logisticapiu officinaverde agricolamonte farmaservizi gestionipro contabilita360
alfacert omegasistemi deltaimpianti nordimpianti sudservizi centroanalisi""".split()

ALIAS_AZIENDE = """Alfaservizi|Borealis Consulting|Castelverde Impianti|Delta Progetti|Edilnova|Ferrovecchio Logistica|
Gamma Sistemi|Idrotermica Padana|Lunaria Software|Meridiana Servizi|Nordest Forniture|Orizzonte Costruzioni|
Polaris Ingegneria|Quadrifoglio Tessile|Rivabella Alimentari|Solaria Energia|Tecnoverde|Ulivo Distribuzione|
Valmora Trasporti|Zefiro Meccanica""".replace("\n", "").split("|")

FORME_SOCIETARIE = r"S\.?\s?r\.?\s?l\.?(?:\s?s\.?)?|S\.?\s?p\.?\s?A\.?|S\.?\s?n\.?\s?c\.?|S\.?\s?a\.?\s?s\.?|S\.?\s?s\.?|Soc\.\s?Coop\.?|Società Cooperativa|Società Semplice|Onlus|S\.?\s?c\.?\s?a\.?\s?r\.?\s?l\.?"

TITOLI = r"(?:[Ss]ig(?:\.ra|\.na|nora|nore|nor|\.)|SIG(?:\.RA|\.)|[Dd]ott(?:\.ssa|oressa|ore|or|\.)|DOTT\.(?:SSA)?|[Dd]r\.|[Aa]vv(?:\.to|\.)|AVV\.|[Pp]rof(?:\.ssa|essoressa|essore|\.)|[Ii]ng\.|[Gg]eom\.|[Rr]ag\.|[Aa]rch\.|[Oo]n\.|[Nn]otaio|[Mm]aestro|[Mm]aestra|[Ss]ignorina|[Dd]on|[Ss]uor|[Cc]av\.|[Cc]omm\.|[Mm]ons\.|[Pp]\.\s?[Ii]\.|[Pp]er\.\s?[Ii]nd\.|[Mm]ister|[Mm]r\.|[Mm]rs\.|[Mm]s\.)"
TITOLI_FEMMINILI = ("sig.ra", "sig.na", "signora", "signorina", "dott.ssa", "dottoressa", "prof.ssa",
                    "professoressa", "maestra", "suor", "mrs.", "ms.", "avv.ta", "la sottoscritta", "nata")

# Parole che, prima di un nome, lo rendono quasi certamente una persona.
INDIZI_PERSONA = (r"(?:il\s+sottoscritto|la\s+sottoscritta|io\s+sottoscritt[oa]|nat[oa]\s+(?:a|il)|paziente|"
                  r"dipendente|lavorat(?:ore|rice)|assistit[oa]|ricorrente|resistente|convenut[oa]|attore|attrice|"
                  r"in\s+persona\s+d(?:i|el|ella)|rappresentat[oa]\s+da|figli[oa]\s+di|coniuge|moglie|marito|"
                  r"vedov[oa]|erede|testimone|teste|imputat[oa]|indagat[oa]|persona\s+offesa|signor[ae]?|"
                  r"gentile|egregi[oa]|car[oa]|spett\.?(?:le)?|a\s+cura\s+di|redatto\s+da|firmato|f\.to|"
                  r"il\s+medico|la\s+dottoressa|il\s+dottore|l'avvocato|l'avv\.|amministratore|legale\s+rappresentante|"
                  r"titolare|socio|socia|presidente|segretari[oa]|relatore|relatrice|presenti|assente|"
                  r"intestat(?:o|a|ario|aria)\s+a|a\s+favore\s+di|nei\s+confronti\s+di|contro|da\s+parte\s+di|"
                  r"ciao|salve|grazie|dear|hi)")

ETICHETTE_PERSONA = r"(?:nome\s+e\s+cognome|cognome\s+e\s+nome|cognome\s*/\s*nome|nome\s*/\s*cognome|nominativo|nome|cognome|paziente|dipendente|lavoratore|lavoratrice|assistito|assistita|intestatario|intestataria|cliente|richiedente|dichiarante|contraente|beneficiario|beneficiaria|titolare|firmatario|medico\s+curante|referente|da|a|cc|from|to)"

PATOLOGIE = """diabete|diabete mellito|ipertensione|ipertensione arteriosa|epilessia|depressione|disturbo bipolare|
schizofrenia|HIV|AIDS|epatite B|epatite C|tumore|carcinoma|neoplasia|leucemia|linfoma|melanoma|sclerosi multipla|
morbo di Parkinson|Parkinson|Alzheimer|demenza|cardiopatia ischemica|infarto miocardico|ictus|BPCO|asma|
insufficienza renale|cirrosi|anoressia|bulimia|tossicodipendenza|alcolismo|disturbo d'ansia|autismo|
sindrome di Down|fibrosi cistica|celiachia|morbo di Crohn|colite ulcerosa|artrite reumatoide|lupus|psoriasi|
gravidanza|interruzione volontaria di gravidanza|aborto|sieropositivo|sieropositività|obesità|ipotiroidismo|
ipertiroidismo|fibrillazione atriale|scompenso cardiaco|polmonite|COVID-19|tubercolosi|osteoporosi|ernia del disco|
frattura del femore""".replace("\n", "").split("|")


# ------------------------------------------------------------------ dizionari estesi (sosia/dizionari), solo per riconoscere
def _righe_diz(nome: str) -> list[str]:
    from pathlib import Path
    p = Path(__file__).with_name("dizionari") / nome
    if not p.exists():
        return []
    return [r.strip() for r in p.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]


LUOGHI_IT = {norm(r.split(";")[0]) for f in ("comuni_it.txt", "frazioni_it.txt", "citta_mondo_it.txt") for r in _righe_diz(f)}
LUOGHI_IT |= {norm(c[0]) for c in COMUNI}
AMBIGUI_LUOGHI_IT = {norm(x) for x in _righe_diz("ambigui_it.txt")}
_NOMI_DIZ = [r.split(";") for f in ("nomi.txt", "diminutivi.txt") for r in _righe_diz(f) if ";" in r]
NOMI_EXTRA_M = {norm(n) for n, g in _NOMI_DIZ if g.strip() in ("M", "U")}
NOMI_EXTRA_F = {norm(n) for n, g in _NOMI_DIZ if g.strip() in ("F", "U")}
COGNOMI_EXTRA = {norm(r) for r in _righe_diz("cognomi.txt")}
AMBIGUI_NOMI = {norm(r) for r in _righe_diz("ambigui_nomi.txt")}
NOMI_PAROLA |= AMBIGUI_NOMI & (NOMI_EXTRA_M | NOMI_EXTRA_F)
COGNOMI_PAROLA |= AMBIGUI_NOMI
LUOGHI_IT -= set()  # (i luoghi restano separati dai nomi: «Ferrara» è città e cognome)
# 0.6.0: elenchi ufficiali (scripts/build_dictionaries.py; fonti e licenze in NOTICE e dizionari/FONTI.json). Restano
# SEPARATI dagli elenchi di prima: valgono solo con un contesto (preposizione, «frazione», «nato a», CAP, sigla), così
# «Re», «Ponte», «Calendasco» non diventano luoghi ovunque e le parole comuni del prefiltro non cambiano.
ISTAT_COMUNI = [tuple(r.split(";")) for r in _righe_diz("istat_comuni.txt") if r.count(";") == 2]
COMUNI_UFF = {norm(c[0]) for c in ISTAT_COMUNI} - LUOGHI_IT
CATASTALE_COMUNE = {c[2]: (c[0], c[1]) for c in ISTAT_COMUNI}
LOCALITA_UFF = {norm(r.split(";")[0]) for r in _righe_diz("istat_localita.txt")} - LUOGHI_IT - COMUNI_UFF
_GREZZE_IT = {norm(r) for r in _righe_diz("parole_comuni_it.txt") + _righe_diz("parole_comuni_en.txt")}
NOMI_UFF = {norm(r) for r in _righe_diz("wikidata_nomi_it.txt")} - _GREZZE_IT - LUOGHI_IT - COMUNI_UFF
COGNOMI_UFF = {norm(r) for r in _righe_diz("wikidata_cognomi_it.txt")} - _GREZZE_IT - LUOGHI_IT - COMUNI_UFF
NON_NOMI |= {norm(x) for x in "Fg Part Sub Sez Foglio Particella Particelle Mappale Mappali Subalterno Sezione Categoria Classe Vani Rendita".split()}
