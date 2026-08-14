# V76 pre-workstation checklist

Before handing the runner to the workstation:

- latest branch HEAD verified remotely;
- Linux V76 end-to-end CI success on that HEAD;
- Windows V76 end-to-end CI success on that HEAD;
- runner syntax success;
- frozen C3 and causality static guards success;
- no LightGBM/XGBoost/broker-order path in V76;
- canonical `.venv` and store are required by runner;
- verified-cache reuse is SHA/report gated;
- user receives one Git Bash runner only.