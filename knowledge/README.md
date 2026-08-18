# Rafaela Knowledge Base

Markdown πρότυπα και διαδικασίες που αναζητά η Rafaela μέσω `search_knowledge`.

## Περιεχόμενα
| Αρχείο | Θέμα |
|--------|------|
| `email-follow-up-meeting.md` | Follow-up μετά από meeting |
| `email-intro-client.md` | Intro σε νέο πελάτη |
| `email-reminder-payment.md` | Υπενθύμιση πληρωμής |
| `meeting-agenda-template.md` | Agenda |
| `meeting-notes-template.md` | Πρακτικά |
| `out-of-office.md` | OOO μήνυμα |
| `escalation-support.md` | Escalation / security |
| `company-tone-of-voice.md` | Τόνος επικοινωνίας |
| `weekly-status-update.md` | Εβδομαδιαίο status |

## Πώς προσθέτεις γνώση
1. Βάλε νέο `.md` σε αυτόν τον φάκελο.  
2. Ξεκίνα με τίτλο `# …` και προαιρετικά `**Tags:** …`.  
3. Κάνε restart / περίμενε cache reload — το keyword search διαβάζει τα αρχεία αμέσως.  
4. Semantic index: με το stack up τρέχει αυτόματα στο startup. Επαν-index:
   `make index-knowledge`  
   ή `POST /api/v1/knowledge/index?recreate=true`  
   Χωρίς OpenAI embeddings χρησιμοποιείται hashed fallback· το keyword search μένει πάντα διαθέσιμο.

## Site μέσω Firecrawl (HITL)

Στο chat: «Δες το https://pc4service.gr/ και αποθήκευσέ το στη γνώση».  
Η Rafaela σκραπάρει δημόσιες σελίδες και ζητά **Έγκριση**. Μετά την έγκριση γράφεται `website-pc4service-gr.md` και γίνεται index στο Qdrant.  
Όχι CRM / login / admin. Χρειάζεται `FIRECRAWL_API_KEY`.

## Σημείωση
Μην βάζεις secrets, passwords ή προσωπικά δεδομένα πελατών εδώ.
