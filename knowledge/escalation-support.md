# Διαδικασία: Escalation υποστήριξης / συμβάντων

**Tags:** support, escalation, incident, SLA, wordfence, security  
**Γλώσσα:** EL  

## Πότε κάνουμε escalate
- Security alerts (π.χ. brute-force, lockouts, data export requests)  
- Υπηρεσία down / πελάτης blocked  
- Οικονομικά θέματα με προθεσμία (ληξιπρόθεσμα, χαμηλό υπόλοιπο κρίσιμης υπηρεσίας)  
- Παράπονο πελάτη χωρίς απάντηση > 1 εργάσιμη ημέρα  

## Επίπεδα
| Επίπεδο | Παράδειγμα | Ενέργεια |
|---------|------------|----------|
| L1 | Πληροφοριακό newsletter | Αρχείο / χαμηλή προτεραιότητα |
| L2 | Ticket αξιολόγησης, backup success | Σημείωση, optional follow-up |
| L3 | Security alert, failed logins | Άμεσος έλεγχος + ενημέρωση υπευθύνου |
| L4 | Data breach / legal | Άμεσο escalate σε management + DPO path |

## Template εσωτερικής ενημέρωσης

```
[ESCALATION] [L3/L4] — [σύντομος τίτλος]
Πηγή: [email/συστήμα]
Ώρα: […]
Σύνοψη: […]
Επίδραση: […]
Προτεινόμενη ενέργεια: […]
Χρειάζεται απόφαση από: […]
```

## Οδηγίες προς Rafaela
- Σε Wordfence / Google data archive / lockout: σήμανε L3 και πρότεινε έλεγχο.  
- Μην πανικοβάλλεις· δώσε γεγονότα + next step.  
- Μην κοινοποιείς ευαίσθητα credentials.
