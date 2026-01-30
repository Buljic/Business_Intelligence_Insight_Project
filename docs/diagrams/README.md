# BI Project Diagrams

## 📊 Available Diagrams

This folder contains professional draw.io diagrams for presentation and documentation.

### 1. **complete_architecture.drawio**
**Complete BI Platform Architecture**

Shows the entire system from data sources to visualization:
- Layer 1: CSV Data Sources
- Layer 2: Staging (Raw Data)
- Layer 3: Star Schema (Data Warehouse)
- Layer 4: BI Marts (Aggregated)
- Layer 5: Machine Learning Pipeline
- Layer 6: Visualization & Control

**Use for:** High-level system overview, architectural presentations

---

### 2. **rfm_segmentation.drawio**
**RFM Customer Segmentation Strategy**

Detailed breakdown of RFM analysis:
- 3 Core Metrics (Recency, Frequency, Monetary)
- 8 Customer Segments with characteristics
- Business actions for each segment
- Value proposition and ROI justification

**Use for:** Marketing strategy, customer analytics presentations

---

### 3. **ml_forecasting_flow.drawio**
**Machine Learning Pipeline**

Complete ML workflow:
- Input: mart_daily_kpis
- Feature Engineering steps
- Prophet Forecasting (14-day predictions)
- Isolation Forest (Anomaly Detection)
- Backtesting & Validation (MAPE, RMSE)
- Model Lifecycle Management
- Output Tables & Views

**Use for:** Technical ML presentations, data science discussions

---

### 4. **star_schema.drawio** *(existing)*
**Star Schema ERD**

Entity-Relationship Diagram showing:
- fact_sales (center)
- 4 Dimensions (date, customer, product, country)
- Foreign key relationships
- Field details

**Use for:** Database design, data modeling presentations

---

### 5. **etl_flow.drawio** *(existing)*
**ETL Process Flow**

Step-by-step ETL pipeline visualization

**Use for:** Data engineering, ETL process explanation

---

## 🖼️ Converting to PNG/PDF

### Method 1: draw.io Desktop App
1. Download from: https://github.com/jgraph/drawio-desktop/releases
2. Open `.drawio` file
3. File → Export as → PNG/PDF
4. Settings:
   - **Resolution:** 300 DPI (high quality)
   - **Border Width:** 10px
   - **Transparent background:** ✓ (optional)

### Method 2: draw.io Web (diagrams.net)
1. Open https://app.diagrams.net/
2. File → Open from → This Device
3. Select `.drawio` file
4. File → Export as → PNG/PDF
5. Choose quality settings

### Method 3: Command Line (Headless)
```bash
# Install draw.io desktop
# Then use CLI export

drawio -x -f png -o complete_architecture.png complete_architecture.drawio
drawio -x -f pdf -o complete_architecture.pdf complete_architecture.drawio
```

### Recommended Settings for Presentations
- **Format:** PNG with transparent background
- **Resolution:** 300 DPI
- **Size:** Original (don't scale)
- **Quality:** Maximum

---

## 📋 Presentation Tips

### PowerPoint Integration
1. Export diagrams as PNG (300 DPI)
2. Insert → Pictures
3. Use "Remove Background" if needed
4. Animate entrance for sections

### PDF Reports
1. Export as PDF directly
2. Full page, landscape orientation
3. Include in appendix or technical sections

### Live Demo Alternative
1. Open `.drawio` files in https://app.diagrams.net/
2. Use presentation mode (View → Lightbox)
3. Full-screen browser for live presentation

---

## 🎨 Diagram Color Scheme

**Consistency across all diagrams:**
- **Data Sources:** Purple (#e1d5e7)
- **Processing:** Yellow (#fff2cc)
- **Storage:** Blue (#dae8fc)
- **BI Marts:** Orange (#ffe6cc)
- **ML Components:** Purple (#e1d5e7)
- **Visualization:** Mixed
- **Success/Good:** Green (#d5e8d4)
- **Warning:** Orange (#ffe6cc)
- **Error/Risk:** Red (#f8cecc)

---

## 📝 Quick Reference

| Diagram | Purpose | Audience | Time |
|---------|---------|----------|------|
| complete_architecture | System overview | All stakeholders | 3-5 min |
| rfm_segmentation | Marketing strategy | Business/Marketing | 4 min |
| ml_forecasting_flow | ML pipeline | Technical/Data Science | 4-5 min |
| star_schema | Database design | Technical/DBA | 2-3 min |
| etl_flow | ETL process | Data Engineers | 2-3 min |

**Total presentation time with all diagrams:** ~15-20 minutes

---

## 🔄 Updating Diagrams

1. Open in draw.io (desktop or web)
2. Make changes
3. Save `.drawio` file
4. Re-export to PNG/PDF
5. Update PowerPoint/PDF documents

**Version control:** Keep `.drawio` source files in this folder

---

## ✅ Pre-Presentation Checklist

- [ ] All diagrams exported to PNG (300 DPI)
- [ ] Backup PDFs created
- [ ] Diagrams embedded in PowerPoint
- [ ] Test on presentation screen/projector
- [ ] Print handouts (if needed)
- [ ] Have backup on USB drive
- [ ] Browser tabs ready for live demo (diagrams.net)

---

**Created:** January 30, 2026
**Author:** BI Project Team
**Format:** draw.io (XML-based, editable)
**License:** Educational use
