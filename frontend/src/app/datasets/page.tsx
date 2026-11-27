// Datasets comparison page — Pima, NHANES, and ICMR-INDIAB (+ LASI external validation status)
"use client";
import { useEffect, useState } from "react";
import { AlertTriangle, Database } from "lucide-react";

interface IndiaStatus {
  permission_status: string;
  dataset_source: string;
  intended_population: string;
  external_validation: string;
  blockers: string[];
}

export default function DatasetsPage() {
  const [indiaStatus, setIndiaStatus] = useState<IndiaStatus | null>(null);

  useEffect(() => {
    fetch("/api/dms/api/v1/india-screening/status")
      .then((r) => r.json())
      .then(setIndiaStatus)
      .catch(() => {});
  }, []);

  const comparisonRows = [
    [
      "Model Label",
      "Historical Pima research benchmark",
      "US population research benchmark",
      "Large US survey research benchmark (CDC BRFSS)",
      "ICMR-INDIAB Indian adult research model",
    ],
    [
      "Country / Setting",
      "United States (Phoenix, Arizona)",
      "United States (national civilian non-institutionalised)",
      "United States (CDC BRFSS telephone health survey)",
      "India (31 states & union territories, urban & rural)",
    ],
    [
      "Survey / Years",
      "Historical cohort (1965–1990s benchmark)",
      "NHANES Cycle J (2017–2018)",
      "CDC BRFSS (UCI Dataset ID 891)",
      "ICMR-INDIAB (2008–2020 phased survey)",
    ],
    [
      "Sample Size",
      "768 participants",
      "4,900 eligible adults (of 9,254 raw)",
      "253,680 survey records (21 features)",
      "~113,043 participants (pending authorised access)",
    ],
    [
      "Age & Sex Eligibility",
      "Women aged 21+ of Pima heritage only",
      "Men and women aged 21+ (age top-coded at 80)",
      "US adult survey respondents (18+)",
      "Men and women aged 20+ (do not extrapolate to 18–19)",
    ],
    [
      "Target Definition",
      "Binary diabetes test outcome within 5 years",
      "DIQ010 == 1 (non-gestational) OR HbA1c >= 6.5%",
      "Diabetes_binary: 0 = no diabetes; 1 = prediabetes or diabetes (survey-reported)",
      "Documented WHO criteria (FBG >= 126 mg/dL, 2h OGTT >= 200 mg/dL, or known diabetes)",
    ],
    [
      "Lab Inputs Required?",
      "Yes (oral GTT glucose, insulin, skinfold)",
      "No (non-laboratory anthropometric/lifestyle only)",
      "No (21 survey-reported health indicators)",
      "No (non-laboratory screening predictors only)",
    ],
    [
      "Acquisition / Readiness",
      "Public benchmark (in repo)",
      "Public domain CDC data (trained)",
      "Public UCI ID 891 (trained)",
      indiaStatus?.permission_status ?? "NOT REQUESTED (awaiting DUA)",
    ],
    [
      "Key Limitations",
      "Small, single-sex, single-ethnicity historical cohort; does not represent Indian adults",
      "US population, single cycle, unweighted training; not validated in India",
      "US self-reported survey status; not laboratory-confirmed diabetes; not validated for Indian adults",
      "Authorised individual-level data not yet received; remote/DUA restrictions apply",
    ],
  ];

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">DATASET COMPARISON &amp; PROVENANCE</div>
          <h1>Dataset comparison</h1>
          <p>
            Population scope, survey years, eligibility, diagnostic target definitions, and
            limitations across Pima, NHANES, and ICMR-INDIAB.
          </p>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* 3-Dataset Comparison Table */}
        <div className="card card-pad" style={{ overflowX: "auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <Database size={20} color="var(--primary)" />
            <h2 style={{ margin: 0 }}>Pima vs. NHANES vs. ICMR-INDIAB</h2>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "var(--surface-soft)", borderBottom: "2px solid var(--border)" }}>
                <th style={{ padding: "10px 12px", textAlign: "left", width: 160 }}>Dimension</th>
                <th style={{ padding: "10px 12px", textAlign: "left" }}>Pima (Model 1)</th>
                <th style={{ padding: "10px 12px", textAlign: "left" }}>NHANES (Model 2)</th>
                <th style={{ padding: "10px 12px", textAlign: "left" }}>CDC BRFSS (UCI 891)</th>
                <th style={{ padding: "10px 12px", textAlign: "left" }}>ICMR-INDIAB (Model 3)</th>
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map(([dim, pima, nhanes, brfss, india]) => (
                <tr key={dim} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "9px 12px", color: "var(--muted)", fontWeight: 650, verticalAlign: "top" }}>{dim}</td>
                  <td style={{ padding: "9px 12px", verticalAlign: "top" }}>{pima}</td>
                  <td style={{ padding: "9px 12px", verticalAlign: "top" }}>{nhanes}</td>
                  <td style={{ padding: "9px 12px", verticalAlign: "top" }}>{brfss}</td>
                  <td style={{ padding: "9px 12px", verticalAlign: "top" }}>{india}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ICMR-INDIAB Governance */}
        <div className="card card-pad">
          <h2 style={{ margin: "0 0 10px" }}>ICMR-INDIAB Governance &amp; Access Status</h2>
          <div className="note note-warn" style={{ marginBottom: 14 }}>
            <AlertTriangle size={16} />
            <p style={{ margin: 0, fontSize: 13 }}>
              <strong>Status: {indiaStatus?.permission_status ?? "NOT REQUESTED"}.</strong>{" "}
              The official NHRDR portal (<code>https://nhrdr.icmr.org.in/datasets/icmr-indiab</code>)
              does not distribute raw individual-level records via public query. No fake or substituted
              data have been used.
            </p>
          </div>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--muted)", lineHeight: 1.7 }}>
            <li>Official repository: https://nhrdr.icmr.org.in/datasets/icmr-indiab</li>
            <li>Primary publication: https://pubmed.ncbi.nlm.nih.gov/37301218/</li>
            <li>Cluster-safe evaluation: Grouped by PSU/cluster ID with sampling strata and weights preserved.</li>
            <li>Private data folder: <code>data/private/indiab/</code> (excluded from Git via <code>.gitignore</code>).</li>
          </ul>
        </div>

        {/* External Validation / LASI */}
        <div className="card card-pad">
          <h2 style={{ margin: "0 0 8px" }}>External Validation (LASI Investigation)</h2>
          <p style={{ margin: "0 0 10px", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
            <strong>{indiaStatus?.external_validation ?? "External validation has not yet been completed."}</strong>
          </p>
          <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
            The Longitudinal Ageing Study in India (LASI) covers older adults aged 45+ using dried-blood-spot
            HbA1c and a distinct sampling design, whereas ICMR-INDIAB covers adults aged 20+ using WHO
            fasting/2-h glucose protocols. They are not combined automatically; any future external
            validation requires explicit age-band (45+), target, and predictor harmonisation.
          </p>
        </div>
      </div>
    </>
  );
}
