# ApplySure

🌐 **Live Website:** https://applysure-mfin.onrender.com/

ApplySure is a Django-based web application that compares PDF documents, identifies matching and mismatched information, explains field differences, and generates downloadable PDF reports.# ApplySure – Smart Document Comparison & Verification System

ApplySure is a Django-based web application that compares two PDF documents, identifies field-level differences, explains the possible significance of mismatches, and generates a downloadable PDF report.

Unlike basic PDF comparison tools that only highlight differences, ApplySure provides **Smart Field Difference Analysis** to help users understand what differs, why it matters, and what action they can consider next.

## Key Features

### 1. PDF Document Comparison
- Upload two PDF documents for comparison.
- Extract readable text and important fields from both documents.
- Compare corresponding fields and identify matching and mismatching values.

### 2. Smart Field Difference Analysis — Additional Feature
This is the main enhancement in ApplySure beyond basic field comparison.

For detected mismatches, the system provides:

- **Mismatch Classification:** Categorizes the detected field difference.
- **Reason:** Explains what is different between the two values.
- **Recommendation:** Suggests a possible next step based on the detected difference.

**Example:**

| Field | Document 1 | Document 2 |
|---|---|---|
| Address | Visakhapatnam | Hyderabad |
| Amount | 500 | 700 |

Instead of simply displaying different values, ApplySure presents a classification, reason, and recommendation for the detected differences.

*Note: These explanations are rule-based application outputs, not official verification or proof of fraud.*

### 3. Downloadable PDF Comparison Report
- Generate a PDF report containing comparison results.
- Review detected differences in a structured format.
- Download the report for future reference.

### 4. Comparison History
- View previous comparison records.
- Revisit saved comparison results.
- Access the history page to review earlier comparisons.

### 5. Simple Web Interface
- Upload and compare documents through a browser.
- View comparison results in an organized layout.
- Use the application without running separate PDF comparison commands manually.

## What Makes ApplySure Different?

| Basic PDF Comparison Tools | ApplySure |
|---|---|
| Show differences between documents | Compare extracted fields and their values |
| May require users to interpret each mismatch themselves | Provides mismatch classification, reason, and recommendation |
| May focus only on displaying results | Also supports downloadable comparison reports |
| May not include a built-in comparison history | Includes a history page for previous comparisons |

*This comparison describes the intended feature distinction; other products may offer similar capabilities.*

## Technology Stack

- **Programming Language:** Python
- **Backend Framework:** Django
- **PDF Text Extraction:** pypdf
- **PDF Report Generation:** ReportLab
- **Frontend:** HTML and CSS
- **Database:** SQLite

## How It Works

1. Upload two PDF documents.
2. Extract the relevant text and fields.
3. Compare corresponding field values.
4. Identify matching values and mismatches.
5. Display the mismatch classification, reason, and recommendation.
6. Download the PDF comparison report.
7. Review previous comparisons through the history page.

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/rm7104586-ux/ApplySure.git
cd ApplySure
```

### 2. Create and Activate a Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root and add a securely generated Django secret key:

```env
DJANGO_SECRET_KEY=your-secret-key
```

Never commit the real `.env` file or secret key to GitHub.

### 5. Apply Migrations

```bash
python manage.py migrate
```

### 6. Run the Application

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## Project Structure

```text
ApplySure/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── documents/
│   ├── migrations/
│   ├── templates/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── tests.py
├── manage.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Limitations

- Comparison accuracy depends on the text that can be extracted from the uploaded PDFs.
- Scanned documents may require OCR support.
- Classification and recommendations are intended to assist review and do not replace official document verification.
- The current project is designed for PDF document comparison.

## Future Enhancements

- OCR support for scanned PDFs.
- Support for additional document formats.
- More advanced field matching.
- Production deployment and improved data storage.

## Author

**Rukanana Mounika**

GitHub: https://github.com/rm7104586-ux

---

**ApplySure — Compare documents, understand differences, and review results more easily.**
