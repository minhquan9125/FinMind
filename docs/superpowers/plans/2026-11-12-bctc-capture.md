# BCTC Capture Implementation Plan

**Goal:** cào BCTC riêng, giữ exactnumbers/raw/requestmetadata, bù kỳ nguồn đã có mà khôngphụthuộcgiá.
**Spec:** docs/sprint5/financial-health/CAPTURE-CONTRACT.md.
**Boundary:** newfinancial_capture.py +existingCLIwrapper +1testfile; noDB/mapping/oldcollector/priceconsumer edits.

- [ ] CAP01 implementdecode_section/financial_records withQA tests; verifyexactprecision, strictsourceidentity/periods, conservativeUNKNOWNmetadata/provenance.
- [ ] CAP02 buildboundedcapture IO andCLIfinancialonly; requests sequential/min2s/max2attempts, noauth/quota retry; all4sectionsrequiredpercompany, immutablebatch.
- [ ] Independentreview+candidatehash/receiptgates; integrateonly3pathsafterreview. Thenrunnewtests+financial102/importJSONtests; avoid broadcleanerhistoricalhashgate alreadyknownfailing.
- [ ] Realcapture10originalsymbols only aftercodecheck;40baselineHTTPcalls (~2sminspacing), stopon401403429. Preserveoriginalsourcehashbefore/after. Freshsnapshotreport+capturecount/latestperiod/metadataabsence audited. NoVPSwrites.
- [ ] UpdateBCTCcheckpoint/context; explainfreshlocalcaptures vsDBpersisted andfieldsnotprovidedbyAPI.

Usernewturn01a1cd7b-6337-7d63-b44e-137047c77859 observedtrustedruntime; exactchat01a1c543-94f8-7c73-9b56-15473db10e76. Newdistinctobjective/workflow s5-bctc-capture-20261112, fixed24calls/7200s/max2repairrounds; nooldworkflowreset. Readskilldiscovery forETLreturnedthroughput/PHI/SEO; notapplicabletoprovenancecapture, nohidden skillenabled. ReusereadECCcoding/TDDguidance.
