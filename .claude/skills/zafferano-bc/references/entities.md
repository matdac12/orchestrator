# Catalogo delle entita' — Business Central Zafferano

Fotografia del service document e di `$metadata` al **2026-08-10**: 231 entity
set pubblicati.

Questo file serve a due domande: *quale entita' mi serve* e *quali campi ha*.
Per capire invece **come le entita' si legano fra loro** — partire da un
codice articolo e arrivare a listini, distinta e venduto — leggi
`relazioni.md`, che e' il documento piu' utile dei due.

## Come leggere questo catalogo

Le 231 entita' non sono tutte uguali per utilita':

- **Dominio operativo** (~84): le pagine che contengono i dati veri. Sono
  quelle che userai quasi sempre.
- **Export Excel** (79): pagine con taglio da export, in larga parte doppioni
  di entita' operative. Utili se ti serve esattamente il taglio di un report
  esistente, altrimenti preferisci l'entita' operativa.
- **Power BI** (58): viste predisposte per il reporting, gia' denormalizzate.
- **OData standard / workflow** (18): API Business Central di serie, non
  personalizzazioni.

I campi sono elencati solo per le entita' core. Per qualunque altra:

```bash
python bc_probe.py fields <NomeEntita>
```

Il probe legge `$metadata` dal vivo ed e' la fonte di verita': se un'entita'
non compare qui, questo file e' vecchio, non e' il tenant a non averla.

## Convenzione dei prefissi sui campi

- nome nudo (`No`, `Description`, `Unit_Price`) — campo Business Central standard;
- `NBT_*` — personalizzazione del partner implementativo (inclusi slot generici
  come `NBT_Code_1`, `NBT_Text_1`: campi jolly, il significato dipende dall'uso);
- `NBT_ZAF_*`, `NBTZAFIT_*` — personalizzazione Zafferano. Qui stanno gli
  attributi illuminotecnici di prodotto e i tre livelli di imballo;
- `*_Filter` in coda — **non sono dati**: sono filtri di pagina. In `$select`
  non restituiscono niente di utile.

## Elenco per dominio

### Anagrafiche (10)

- `Agenti`
- `Company`
- `Dati_Clienti`
- `Enasarco`
- `Fornitori`
- `Mail`
- `Mail_Clienti`
- `Scheda_Fornitore`
- `Scheda_fornitori`
- `SegmentLines`

### Articoli e distinte (8)

- `Articoli`
- `Articoli_Statistici`
- `DBAssemblaggio`
- `DB_Righe`
- `Item`
- `Item_Blocked`
- `Items`
- `Ordini_produzione`

### Listini (6)

- `ListiniAcquisto_righe`
- `ListiniAcquisto_righeLines`
- `ListiniAcquisto_test`
- `Listini_prezzi_vendita_righe`
- `Price_List`
- `Price_ListLines`

### Vendite (22)

- `Cumulate`
- `CumulateLines`
- `Cumulate_Head`
- `ItemSalesAndProfit`
- `ItemSalesByCustomer`
- `Ordini_Resi`
- `Ordini_ResiSalesLines`
- `Ordini_Shopify_Negozi`
- `Ordini_Shopify_NegoziShopifyOrderLines`
- `Ordini_di_Reso`
- `Ordini_di_Vendita`
- `Ordini_di_VenditaSalesLines`
- `Ordini_di_Vendita_Righe`
- `RigheAnalisiVenduto`
- `Righe_Vendite`
- `SalesDashboard`
- `SalesOpportunities`
- `SalesOrder`
- `SalesOrderSalesLines`
- `SalesOrdersBySalesPerson`
- `TopCustomerOverview`
- `righe_sped_cum`

### Acquisti e trasferimenti (2)

- `OC_testate`
- `OrdiniTrasferimento`

### Movimenti e contabilita' (13)

- `AccSchedPL`
- `BankAccountLedgerEntries`
- `ColumnLayoutPL`
- `Cust_LedgerEntries`
- `FALedgerEntries`
- `G_LBudgetEntries`
- `G_LEntries`
- `ItemLedgerEntries`
- `Mov_Valorizzazione`
- `Piano_dei_conti`
- `Res_LedgerEntries`
- `ValueEntries`
- `VendorLedgerEntries`

### Commesse (4)

- `JobLedgerEntries`
- `Job_List`
- `Job_Planning_Lines`
- `Job_Task_Lines`

### Configurazione e tabelle di servizio (11)

- `AccountantPortalActivityCues`
- `AccountantPortalFinanceCues`
- `AccountantPortalUserTasks`
- `Causali`
- `Collocazioni`
- `DimensionSetEntries`
- `DimensionSets`
- `Dimensioni`
- `UM`
- `Ubicazioni`
- `UserTaskSetComplete`

### Export Excel (79)

- `Articoli_Statistici_Excel`
- `Categorie_articoli_Excel`
- `Codici_postali_Excel`
- `Collocazioni_Excel`
- `Contratto_provvigionale_Excel`
- `Contratto_provvigionale_ExcelLines`
- `DB_produzione_Excel`
- `DB_produzione_ExcelProdBOMLine`
- `Dimensioni_di_Default_Excel`
- `Elenco_ABI_CAB_Excel`
- `ExcelTemplateAgedAccountsPayable`
- `ExcelTemplateAgedAccountsReceivable`
- `ExcelTemplateBalanceSheet`
- `ExcelTemplateCashFlowStatement`
- `ExcelTemplateIncomeStatement`
- `ExcelTemplateRetainedEarnings`
- `ExcelTemplateTrialBalance`
- `ExcelTemplateViewCompanyInformation`
- `Fattura_vendita_Excel`
- `Fattura_vendita_ExcelSalesLines`
- `Fatture_vendita_reg__Excel`
- `Fatture_vendita_reg__ExcelSalesInvLines`
- `Gestione_alberi_B2B_Excel`
- `Giornali_di_registrazione_pagamenti_Excel`
- `Icone_Certificazione_Excel`
- `Icone_Imballo_Articolo_Excel`
- `Inventario_fisico_ADCS_Excel`
- `Lingue_Excel`
- `Lista_GTIN_Excel`
- `Lista_marche_Excel`
- `Lista_riferimento_articolo_Excel`
- `Listino_prezzi_di_vendita_Excel`
- `Listino_prezzi_di_vendita_ExcelLines`
- `Mov_contabili_articoli_Excel`
- `Mov_contabili_provvigioni_Excel`
- `Mov_contabili_provvigioni_stornati_Excel`
- `Movimenti_C_G_Excel`
- `Movimenti_IVA_Excel`
- `Movimenti_contabili_clienti_Excel`
- `Movimenti_contabili_fornitori_Excel`
- `Movimenti_log_modifiche_Excel`
- `Nr_serie_Excel`
- `Ordine_di_reso_vendita_Excel`
- `Ordine_di_reso_vendita_ExcelSalesLines`
- `Ordine_vendita_Excel`
- `Ordine_vendita_ExcelSalesLines`
- `Paesi_Aree_geografiche_Excel`
- `Price_List_Lines_Excel`
- `Purchase_InvoicePurchLines_Excel`
- `Purchase_Order_Line_Excel`
- `Registrazione_COGE_Simulate_Excel`
- `Registrazioni_COGE_Excel`
- `Registrazioni_inventario_fisico_Excel`
- `Registrazioni_magazzino_Excel`
- `Ricambi_Excel`
- `Righe_Excel`
- `Righe_analisi_venduto_Excel`
- `Righe_fatt_acq_registrate_Excel`
- `Righe_vendita_Excel`
- `Sales_Order_Line_Excel`
- `Sales_QuoteSalesLines_Excel`
- `Scheda_C_C_bancario_Excel`
- `Scheda_Impostazioni_utente_Excel`
- `Scheda_Ubicazione_Excel`
- `Scheda_agenti_addetti_acq__Excel`
- `Scheda_articolo_Excel`
- `Scheda_categoria_articolo_Excel`
- `Scheda_categoria_articolo_ExcelAttributes`
- `Scheda_cliente_Excel`
- `Scheda_cliente_Excel_2`
- `Scheda_fornitore_Excel`
- `Scheda_unità_di_stockkeeping_Excel`
- `Spedire_a_Indirizzo_Excel`
- `Spedizione_Cumulativa_Excel`
- `Spedizione_Cumulativa_ExcelLines`
- `Spedizioni_vendita_registrate_Excel`
- `Spedizioni_vendita_registrate_ExcelSalesShipmLines`
- `Traduzioni_Articolo_Excel`
- `Valori_dimensioni_Excel`

### Power BI (58)

- `PBI_BankAccount`
- `PBI_BankAccountLedgerEntry`
- `PBI_CalendarEntry`
- `PBI_CapLedgerEntry`
- `PBI_CashFlowAccount`
- `PBI_CashFlowWorksheetLine`
- `PBI_CustLedgerEntries`
- `PBI_Customer`
- `PBI_DetCustLedgEntry`
- `PBI_DetVendorLedgEntry`
- `PBI_FixedAsset`
- `PBI_GLAccount`
- `PBI_GLEntry`
- `PBI_Item`
- `PBI_ItemCharge`
- `PBI_PurchCrMemo`
- `PBI_PurchInvoice`
- `PBI_PurchOrder`
- `PBI_PurchOutstanding`
- `PBI_PurchRcpt`
- `PBI_PurchaseHst`
- `PBI_RoutingLine`
- `PBI_SalesCrMemo`
- `PBI_SalesHst`
- `PBI_SalesInvoice`
- `PBI_SalesOrder`
- `PBI_SalesOutstanding`
- `PBI_SalesShipment`
- `PBI_SimBankAccountEntry`
- `PBI_SimGLEntry`
- `PBI_Vendor`
- `PBI_VendorLedgerEntry`
- `Power_BI_Aged_Acc_Payable`
- `Power_BI_Aged_Acc_Receivable`
- `Power_BI_Aged_Inventory_Chart`
- `Power_BI_Cust_Item_Ledg_Ent`
- `Power_BI_Cust_Ledger_Entries`
- `Power_BI_Customer_List`
- `Power_BI_GL_Amount_List`
- `Power_BI_GL_BudgetedAmount`
- `Power_BI_Item_Purchase_List`
- `Power_BI_Item_Sales_List`
- `Power_BI_Job_Act_v_Budg_Cost`
- `Power_BI_Job_Act_v_Budg_Price`
- `Power_BI_Job_Profitability`
- `Power_BI_Jobs_List`
- `Power_BI_Purchase_Hdr_Vendor`
- `Power_BI_Purchase_List`
- `Power_BI_Sales_Hdr_Cust`
- `Power_BI_Sales_List`
- `Power_BI_Sales_Pipeline`
- `Power_BI_Top_5_Opportunities`
- `Power_BI_Top_Cust_Overview`
- `Power_BI_Vend_Item_Ledg_Ent`
- `Power_BI_Vendor_Ledger_Entries`
- `Power_BI_Vendor_List`
- `Power_BI_WorkDate_Calc`
- `powerbifinance`

### OData standard / workflow (18)

- `purchaseDocumentLines`
- `purchaseDocuments`
- `purchaseDocumentsworkflowPurchaseDocumentLines`
- `salesDocumentLines`
- `salesDocuments`
- `salesDocumentsworkflowSalesDocumentLines`
- `workflowCustomers`
- `workflowGenJournalBatches`
- `workflowGenJournalLines`
- `workflowItems`
- `workflowPurchaseDocumentLines`
- `workflowPurchaseDocuments`
- `workflowPurchaseDocumentsworkflowPurchaseDocumentLines`
- `workflowSalesDocumentLines`
- `workflowSalesDocuments`
- `workflowSalesDocumentsworkflowSalesDocumentLines`
- `workflowVendors`
- `workflowWebhookSubscriptions`


## Campi delle entita' core

### `Articoli` — 210 campi

**Campi Business Central standard** (45)

`No`, `Description`, `Description_2`, `Type`, `InventoryField`, `Created_From_Nonstock_Item`, `Substitutes_Exist`, `Stockkeeping_Unit_Exists`, `Assembly_BOM`, `Production_BOM_No`, `Routing_No`, `Base_Unit_of_Measure`, `Shelf_No`, `Costing_Method`, `Cost_is_Adjusted`, `Standard_Cost`, `Unit_Cost`, `Last_Direct_Cost`, `Price_Profit_Calculation`, `Profit_Percent`, `Unit_Price`, `Inventory_Posting_Group`, `Gen_Prod_Posting_Group`, `VAT_Prod_Posting_Group`, `Item_Disc_Group`, `Vendor_No`, `Vendor_Item_No`, `Tariff_No`, `Search_Description`, `Overhead_Rate`, `Indirect_Cost_Percent`, `Item_Category_Code`, `Blocked`, `Last_Date_Modified`, `Sales_Unit_of_Measure`, `Replenishment_System`, `Purch_Unit_of_Measure`, `Lead_Time_Calculation`, `Manufacturing_Policy`, `Flushing_Method`, `Assembly_Policy`, `Item_Tracking_Code`, `Default_Deferral_Template_Code`, `Coupled_to_Dataverse`, `GTIN`

**Personalizzazioni partner (NBT_*)** (32)

`NBT_MDW_Status_Code`, `NBT_Description_2`, `NBT_Tool`, `NBT_Code_1`, `NBT_Code_2`, `NBT_Code_3`, `NBT_Code_4`, `NBT_Code_5`, `NBT_Code_6`, `NBT_Code_7`, `NBT_Code_8`, `NBT_Code_9`, `NBT_Text_1`, `NBT_Text_2`, `NBT_Text_3`, `NBT_Text_4`, `NBT_Text_5`, `NBT_Boolean_1`, `NBT_Boolean_2`, `NBT_Boolean_3`, `NBT_Boolean_4`, `NBT_Boolean_5`, `NBT_Integer_1`, `NBT_Integer_2`, `NBT_Integer_3`, `NBT_Integer_4`, `NBT_Decimal_1`, `NBT_Decimal_2`, `NBT_Decimal_3`, `NBT_Date_1`, `NBT_Date_2`, `NBT_Date_3`

**Personalizzazioni Zafferano (NBT_ZAF_*)** (105)

`NBT_ZAF_CompanyPriceList`, `NBT_ZAF_FOB_Qty`, `NBT_ZAF_Qty_on_Sales_Order`, `NBT_ZAF_Qty_on_Purch_Order`, `NBT_ZAF_Service_Item_Group`, `NBT_ZAF_Statistic_Item`, `NBT_ZAF_ENU_Description`, `NBT_ZAF_Subject_to_RAEE`, `NBT_ZAF_Battery_Item`, `NBT_ZAF_Usb_Type`, `NBT_ZAF_UsbTypeDesc`, `NBT_ZAF_Made_In`, `NBT_ZAF_MadeInDesc`, `NBT_ZAF_Product_Line`, `NBT_ZAF_ProductLineDesc`, `NBT_ZAF_Finish`, `NBT_ZAF_Variant`, `NBT_ZAF_Style`, `NBT_ZAF_StyleDesc`, `NBT_ZAF_Brand`, `NBT_ZAF_BrandDesc`, `NBT_ZAF_Collection`, `NBT_ZAF_Collection_2`, `NBT_ZAF_Product_Type`, `NBT_ZAF_ProductTypeDesc`, `NBT_ZAF_Classification`, `NBT_ZAF_Family`, `NBT_ZAF_FamilyDesc`, `NBT_ZAF_Novelty`, `NBT_ZAF_To_Be_eliminated`, `NBT_ZAF_Diameter`, `NBT_ZAF_Side_1`, `NBT_ZAF_Side_2`, `NBT_ZAF_Partial_Height`, `NBT_ZAF_Total_Height`, `NBT_ZAF_Product_Finishing`, `NBT_ZAF_ProductFinishingDesc`, `NBT_ZAF_Product_RAL`, `NBT_ZAF_Product_Protrusion`, `NBT_ZAF_Main_Material`, `NBT_ZAF_MainMaterialDesc`, `NBT_ZAF_Main_Processing`, `NBT_ZAF_MainProcessingDesc`, `NBT_ZAF_Empty_Code`, `NBT_ZAF_EmptyCodeDesc`, `NBT_ZAF_Hole_instal_recessed`, `NBT_ZAF_Product_Capacity_CL`, `NBT_ZAF_Source`, `NBT_ZAF_SourceDesc`, `NBT_ZAF_Source_Type`, `NBT_ZAF_SourceTypeDesc`, `NBT_ZAF_Total_Watt`, `NBT_ZAF_Led_Source_Watt`, `NBT_ZAF_Color_Temperature`, `NBT_ZAF_Lamp_Lumens`, `NBT_ZAF_Lumens_Light_Source`, `NBT_ZAF_Light_Band_Corner`, `NBT_ZAF_IRC_CRI`, `NBT_ZAF_Led_Power_Supply`, `NBT_ZAF_Product_Code`, `NBT_ZAF_ProductCodeDesc`, `NBT_ZAF_Source_Code`, `NBT_ZAF_SourceCodeDesc`, `NBT_ZAF_Light_Sour_Energy_Cls`, `NBT_ZAF_Led_Source_Watt_Sr_2`, `NBT_ZAF_Color_Temperature_Sr_2`, `NBT_ZAF_Lumens_Light_Source_S2`, `NBT_ZAF_Light_Band_Corner_Sr_2`, `NBT_ZAF_IRC_CRI_Source_2`, `NBT_ZAF_Light_Sour_Ener_Cls_S2`, `NBT_ZAF_Driver_Code`, `NBT_ZAF_DriverCodeDesc`, `NBT_ZAF_Battery_Code`, `NBT_ZAF_BatteryCodeDesc`, `NBT_ZAF_Supply_Voltage`, `NBT_ZAF_Charger_Driver`, `NBT_ZAF_ChargeDriverDesc`, `NBT_ZAF_Charger_Driver_INPUT`, `NBT_ZAF_Charger_Driver_OUTPUT`, `NBT_ZAF_Frequency`, `NBT_ZAF_Class`, `NBT_ZAF_ClassCodeDesc`, `NBT_ZAF_Dimmable_Product`, `NBT_ZAF_DimmableProductDesc`, `NBT_ZAF_Dimmer_Type`, `NBT_ZAF_Presence_Sensor`, `NBT_ZAF_PresenceSensorDesc`, `NBT_ZAF_Light_Sensor`, `NBT_ZAF_LightSensorDesc`, `NBT_ZAF_Lamp_Lifespan`, `NBT_ZAF_Battery_Type`, `NBT_ZAF_BatteryTypeDesc`, `NBT_ZAF_No_of_Battery_Package`, `NBT_ZAF_Battery_Autonomy`, `NBT_ZAF_Recharge`, `NBT_ZAF_IP`, `NBT_ZAF_IPDesc`, `NBT_ZAF_LK`, `NBT_ZAF_Salt_Spray_Resistance`, `NBT_ZAF_Thermal_Dissipation`, `NBT_ZAF_ThermalDissipationDesc`, `NBT_ZAF_Usage`, `NBT_ZAF_UsageDesc`, `NBT_ZAF_OnPage_Qty_On_Package`, `NBT_ZAF_Available_for_purchase`

**Imballo (tre livelli)** (18)

`NBT_ZAF_Package_1_Net_Weight`, `NBT_ZAF_Package_1_Gross_Weight`, `NBT_ZAF_Package_1_Tare_Weight`, `NBT_ZAF_Package_1_Measure_1`, `NBT_ZAF_Package_1_Measure_2`, `NBT_ZAF_Package_1_Measure_3`, `NBT_ZAF_Package_2_Net_Weight`, `NBT_ZAF_Package_2_Gross_Weight`, `NBT_ZAF_Package_2_Tare_Weight`, `NBT_ZAF_Package_2_Measure_1`, `NBT_ZAF_Package_2_Measure_2`, `NBT_ZAF_Package_2_Measure_3`, `NBT_ZAF_Package_3_Net_Weight`, `NBT_ZAF_Package_3_Gross_Weight`, `NBT_ZAF_Package_3_Tare_Weight`, `NBT_ZAF_Package_3_Measure_1`, `NBT_ZAF_Package_3_Measure_2`, `NBT_ZAF_Package_3_Measure_3`

**Campi filtro (non sono dati: filtrano la pagina)** (10)

`Global_Dimension_1_Filter`, `Global_Dimension_2_Filter`, `Location_Filter`, `Drop_Shipment_Filter`, `Variant_Filter`, `Lot_No_Filter`, `Serial_No_Filter`, `Unit_of_Measure_Filter`, `Package_No_Filter`, `Date_Filter`

### `Fornitori` — 70 campi

**Campi Business Central standard** (35)

`No`, `Name`, `Name_2`, `Address`, `City`, `Responsibility_Center`, `Location_Code`, `Post_Code`, `Country_Region_Code`, `Phone_No`, `Fax_No`, `IC_Partner_Code`, `Contact`, `Purchaser_Code`, `Vendor_Posting_Group`, `Allow_Multiple_Posting_Groups`, `Gen_Bus_Posting_Group`, `VAT_Bus_Posting_Group`, `Payment_Terms_Code`, `Fin_Charge_Terms_Code`, `Currency_Code`, `Language_Code`, `Search_Name`, `Blocked`, `Privacy_Blocked`, `Last_Date_Modified`, `Application_Method`, `Location_Code2`, `Shipment_Method_Code`, `Lead_Time_Calculation`, `Base_Calendar_Code`, `Balance_LCY`, `Balance_Due_LCY`, `Payments_LCY`, `Coupled_to_Dataverse`

**Personalizzazioni partner (NBT_*)** (31)

`NBT_MDW_Status_Code`, `NBT_Code_1`, `NBT_Code_2`, `NBT_Code_3`, `NBT_Code_4`, `NBT_Code_5`, `NBT_Code_6`, `NBT_Code_7`, `NBT_Code_8`, `NBT_Code_9`, `NBT_Text_1`, `NBT_Text_2`, `NBT_Text_3`, `NBT_Text_4`, `NBT_Text_5`, `NBT_Boolean_1`, `NBT_Boolean_2`, `NBT_Boolean_3`, `NBT_Boolean_4`, `NBT_Boolean_5`, `NBT_Integer_1`, `NBT_Integer_2`, `NBT_Integer_3`, `NBT_Integer_4`, `NBT_Decimal_1`, `NBT_Decimal_2`, `NBT_Decimal_3`, `NBT_Date_1`, `NBT_Date_2`, `NBT_Date_3`, `NBT_Balance_At_Date_LCY`

**Campi filtro (non sono dati: filtrano la pagina)** (4)

`Global_Dimension_1_Filter`, `Global_Dimension_2_Filter`, `Currency_Filter`, `Date_Filter`

### `Scheda_Fornitore` — 177 campi

**Campi Business Central standard** (110)

`No`, `Name`, `Name_2`, `Blocked`, `Privacy_Blocked`, `Last_Date_Modified`, `Fiscal_Code`, `Special_Category`, `Balance_LCY`, `BalanceAsCustomer`, `Balance_Due_LCY`, `Document_Sending_Profile`, `Search_Name`, `IC_Partner_Code`, `Purchaser_Code`, `Responsibility_Center`, `Disable_Search_by_Name`, `Company_Size_Code`, `Statistics_Group`, `Sust_Cert_No`, `Sust_Cert_Name`, `Carbon_Pricing_Paid`, `Address`, `Address_2`, `Country_Region_Code`, `City`, `County`, `Post_Code`, `ShowMap`, `Phone_No`, `MobilePhoneNo`, `E_Mail`, `Fax_No`, `Home_Page`, `Our_Account_No`, `Apply_Company_Payment_days`, `Language_Code`, `Format_Region`, `Primary_Contact_No`, `Control16`, `VAT_Registration_No`, `EORI_Number`, `GLN`, `Tax_Liable`, `Tax_Area_Code`, `Pay_to_Vendor_No`, `Invoice_Disc_Code`, `Prices_Including_VAT`, `Price_Calculation_Method`, `Registration_Number`, `Gen_Bus_Posting_Group`, `VAT_Bus_Posting_Group`, `Vendor_Posting_Group`, `Allow_Multiple_Posting_Groups`, `Currency_Code`, `Tax_Representative_Type`, `Tax_Representative_No`, `Resident`, `Residence_Address`, `Residence_Post_Code`, `Residence_City`, `First_Name`, `Last_Name`, `Residence_County`, `Date_of_Birth`, `Birth_Post_Code`, `Birth_City`, `Birth_County`, `Gender`, `Individual_Person`, `Withholding_Tax_Code`, `Social_Security_Code`, `Soc_Sec_Company_Base`, `Soc_Sec_3_Parties_Base`, `Country_of_Fiscal_Domicile`, `Contribution_Fiscal_Code`, `INAIL_Code`, `INAIL_Company_Base`, `INAIL_3_Parties_Base`, `First_Name2`, `Last_Name2`, `Prepayment_Percent`, `Application_Method`, `Payment_Terms_Code`, `Prepmt_Payment_Terms_Code`, `Payment_Method_Code`, `Priority`, `Block_Payment_Tolerance`, `Int_on_Arrears_Code`, `Preferred_Bank_Account_Code`, `Partner_Type`, `Intrastat_Partner_Type`, `Cash_Flow_Payment_Terms_Code`, `Creditor_No`, `Exclude_from_Pmt_Practices`, `Location_Code`, `Shipment_Method_Code`, `Lead_Time_Calculation`, `Base_Calendar_Code`, `Customized_Calendar`, `Over_Receipt_Code`, `Subcontractor`, `Subcontracting_Location_Code`, `Subcontractor_Procurement`, `Linked_to_Work_Center`, `Receive_E_Document_To`, `E_Document_Service_Participation_Ids`, `Default_Trans_Type`, `Default_Trans_Type_Return`, `Def_Transport_Method`

**Personalizzazioni partner (NBT_*)** (60)

`NBT_Expense_Job_Default`, `NBT_Customs`, `NBT_Territory_Code`, `NBT_E_Mail_Pec`, `NBT_IT_Activate_XML_Receipts`, `NBT_QLT_Duty_of_Rating`, `NBT_QLT_ClassificationCode`, `NBT_QLT_Custom_Weighted_Percent`, `NBT_QLT_Qlt_Criteria_Weight_Percent`, `NBT_QLT_Qty_Criteria_Weight_Percent`, `NBT_QLT_Date_Criteria_Weight_Percent`, `NBT_Related_Customer_No`, `NBT_Payment_Bank`, `NBT_Doc_Waiver`, `NBT_Doc_Financial_Voice`, `NBT_Doc_Delay_Day_on_Proceed`, `NBT_Doc_Ignore_Export`, `NBT_Del_rem_Term_Code`, `NBT_Code_1`, `NBT_Code_2`, `NBT_Code_3`, `NBT_Code_4`, `NBT_Code_5`, `NBT_Code_6`, `NBT_Code_7`, `NBT_Code_8`, `NBT_Code_9`, `NBT_Code_10`, `NBT_Text_1`, `NBT_Text_2`, `NBT_Text_3`, `NBT_Text_4`, `NBT_Text_5`, `NBT_Boolean_1`, `NBT_Boolean_2`, `NBT_Boolean_3`, `NBT_Boolean_4`, `NBT_Boolean_5`, `NBT_Integer_1`, `NBT_Integer_2`, `NBT_Integer_3`, `NBT_Integer_4`, `NBT_Decimal_1`, `NBT_Decimal_2`, `NBT_Date_1`, `NBT_Date_2`, `NBT_Date_3`, `NBT_IT_Enasarco_code`, `NBT_IT_Juridical_Figure`, `NBT_IT_Mandate`, `NBT_IT_Enasarco_Contribution`, `NBT_IT_FIRR_Subject`, `NBT_IT_Calculate_Contribution`, `NBT_IT_Enasarco_Registration_No`, `NBT_IT_Starting_Date_Collab`, `NBT_IT_Ending_Date_Collab`, `NBT_IT_Enasarco_Company_Base`, `NBT_IT_Providence_Payable_Amount`, `NBT_IT_Assistance_Payable_Amount`, `NBT_IT_FIRR_Payable_Amount`

**Personalizzazioni Zafferano (NBT_ZAF_*)** (3)

`NBT_ZAF_Closing_Day`, `NBT_ZAF_Reception_Hours`, `NBT_ZAF_Confirmation_Phone_No`

**Campi filtro (non sono dati: filtrano la pagina)** (4)

`Global_Dimension_1_Filter`, `Global_Dimension_2_Filter`, `Currency_Filter`, `Date_Filter`

### `Dati_Clienti` — 266 campi

**Campi Business Central standard** (176)

`No`, `Name`, `Name_2`, `Responsibility_Center`, `Location_Code`, `Post_Code`, `Country_Region_Code`, `Phone_No`, `IC_Partner_Code`, `Contact`, `Salesperson_Code`, `Customer_Posting_Group`, `Allow_Multiple_Posting_Groups`, `Gen_Bus_Posting_Group`, `VAT_Bus_Posting_Group`, `Customer_Price_Group`, `Customer_Disc_Group`, `Payment_Terms_Code`, `Reminder_Terms_Code`, `Fin_Charge_Terms_Code`, `Currency_Code`, `Language_Code`, `Search_Name`, `Credit_Limit_LCY`, `Blocked`, `Privacy_Blocked`, `Last_Date_Modified`, `Application_Method`, `Combine_Shipments`, `Reserve`, `Ship_to_Code`, `Shipping_Advice`, `Shipping_Agent_Code`, `Base_Calendar_Code`, `Balance_LCY`, `Balance_Due_LCY`, `Sales_LCY`, `Payments_LCY`, `Coupled_to_Dataverse`, `Address`, `Address_2`, `Allow_Line_Disc`, `Amount`, `Balance`, `Balance_Due`, `Bill_to_Customer_No`, `Bill_to_No_Of_Archived_Doc`, `Bill_To_No_of_Blanket_Orders`, `Bill_To_No_of_Credit_Memos`, `Bill_To_No_of_Invoices`, `Bill_To_No_of_Orders`, `Bill_To_No_of_Pstd_Cr_Memos`, `Bill_To_No_of_Pstd_Invoices`, `Bill_To_No_of_Pstd_Return_R`, `Bill_To_No_of_Pstd_Shipments`, `Bill_To_No_of_Quotes`, `Bill_To_No_of_Return_Orders`, `Block_Payment_Tolerance`, `Budgeted_Amount`, `Cash_Flow_Payment_Terms_Code`, `Chain_Name`, `City`, `Collection_Method`, `Comment`, `Contact_Graph_Id`, `Contact_ID`, `Contact_Type`, `Contract_Gain_Loss_Amount`, `Copy_Sell_to_Addr_to_Qte_From`, `County`, `Cr_Memo_Amounts`, `Cr_Memo_Amounts_LCY`, `Credit_Amount`, `Credit_Amount_LCY`, `Cumulative_Bank_Receipts`, `Currency_Id`, `Date_of_Birth`, `Debit_Amount`, `Debit_Amount_LCY`, `Disable_Search_by_Name`, `Document_Sending_Profile`, `E_Mail`, `EORI_Number`, `Exclude_from_Pmt_Practices`, `Exposure_LCY`, `Fax_No`, `Fin_Charge_Memo_Amounts_LCY`, `Finance_Charge_Memo_Amounts`, `First_Name`, `Fiscal_Code`, `Format_Region`, `GLN`, `Global_Dimension_1_Code`, `Global_Dimension_2_Code`, `Individual_Person`, `Int_on_Arrears_Code`, `Intrastat_Partner_Type`, `Inv_Amounts_LCY`, `Inv_Discounts_LCY`, `Invoice_Amounts`, `Invoice_Copies`, `Invoice_Disc_Code`, `Last_Modified_Date_Time`, `Last_Name`, `Last_Statement_No`, `Mobile_Phone_No`, `Net_Change`, `Net_Change_LCY`, `No_of_Blanket_Orders`, `No_of_Credit_Memos`, `No_of_Invoices`, `No_of_Orders`, `No_of_Pstd_Credit_Memos`, `No_of_Pstd_Invoices`, `No_of_Pstd_Return_Receipts`, `No_of_Pstd_Shipments`, `No_of_Quotes`, `No_of_Return_Orders`, `No_of_Ship_to_Addresses`, `No_Series`, `Other_Amounts`, `Other_Amounts_LCY`, `Our_Account_No`, `Outstanding_Invoices`, `Outstanding_Invoices_LCY`, `Outstanding_Orders`, `Outstanding_Orders_LCY`, `Outstanding_Serv_Orders_LCY`, `Outstanding_Serv_Invoices_LCY`, `PA_Code`, `Partner_Type`, `Payment_Method_Code`, `Payment_Method_Id`, `Payment_Terms_Id`, `Payments`, `PEC_E_Mail_Address`, `Place_of_Birth`, `Place_of_Export`, `Pmt_Disc_Tolerance_LCY`, `Pmt_Discounts_LCY`, `Pmt_Tolerance_LCY`, `Preferred_Bank_Account_Code`, `Prepayment_Percent`, `Price_Calculation_Method`, `Prices_Including_VAT`, `Primary_Contact_No`, `Print_Statements`, `Priority`, `Profit_LCY`, `Refunds`, `Refunds_LCY`, `Registration_Number`, `Reminder_Amounts`, `Reminder_Amounts_LCY`, `Resident`, `Sell_to_No_Of_Archived_Doc`, `Serv_Shipped_Not_Invoiced_LCY`, `Service_Zone_Code`, `Shipment_Method_Code`, `Shipment_Method_Id`, `Shipped_Not_Invoiced`, `Shipped_Not_Invoiced_LCY`, `Shipping_Agent_Service_Code`, `Shipping_Time`, `Statistics_Group`, `Tax_Area_Code`, `Tax_Area_ID`, `Tax_Liable`, `Tax_Representative_No`, `Tax_Representative_Type`, `Telex_Answer_Back`, `Telex_No`, `Territory_Code`, `Use_GLN_in_Electronic_Document`, `Validate_EU_Vat_Reg_No`, `VAT_Registration_No`

**Personalizzazioni partner (NBT_*)** (56)

`NBT_Boolean_1`, `NBT_Boolean_2`, `NBT_Boolean_3`, `NBT_Boolean_4`, `NBT_Boolean_5`, `NBT_Code_1`, `NBT_Code_10`, `NBT_Code_2`, `NBT_Code_3`, `NBT_Code_4`, `NBT_Code_5`, `NBT_Code_6`, `NBT_Code_7`, `NBT_Code_8`, `NBT_Code_9`, `NBT_Date_1`, `NBT_Date_2`, `NBT_Date_3`, `NBT_Decimal_1`, `NBT_Decimal_2`, `NBT_Decimal_3`, `NBT_Doc_Delay_Day_on_Proceed`, `NBT_Doc_Financial_Voice`, `NBT_Doc_Ignore_Export`, `NBT_Doc_Waiver`, `NBT_E_Mail_Pec`, `NBT_Group_Bonus_Code`, `NBT_Identification_Bonus`, `NBT_Integer_1`, `NBT_Integer_2`, `NBT_Integer_3`, `NBT_Integer_4`, `NBT_Invoice_Group_Code`, `NBT_MDW_Status_Code`, `NBT_Partial__x0026__Closed`, `NBT_Payment_Bank`, `NBT_Related_Vendor_No`, `NBT_Salesperson_Code_2`, `NBT_Shipment_Group_Code`, `NBT_Shipment_Invoice`, `NBT_Text_1`, `NBT_Text_2`, `NBT_Text_3`, `NBT_Text_4`, `NBT_Text_5`, `NBT_B2B_Indoor_Salesperson`, `NBT_IT_Admin_Reference`, `NBT_IT_Avoid_Descr_Line_XML`, `NBT_IT_Avoid_Inv_Disc_in_XML`, `NBT_IT_E_Invoice_Dest_Code`, `NBT_IT_E_Invoice_Vendor_Type`, `NBT_IT_Export_Tag_DatFattColl`, `NBT_IT_PA_Customer`, `NBT_IT_Price_Disc_XML_Line`, `NBT_IT_Self_Invoice`, `NBT_IT_XML_Burdens`

**Personalizzazioni Zafferano (NBT_ZAF_*)** (28)

`NBT_ZAF_CertOfOrigin_Required`, `NBT_ZAF_Closing_Hours`, `NBT_ZAF_Creation_Date`, `NBT_ZAF_Creation_User`, `NBT_ZAF_Customer_Category`, `NBT_ZAF_Customer_Note`, `NBT_ZAF_Default_E_Invoice_Code`, `NBT_ZAF_Exclude_from_Send_Mail`, `NBT_ZAF_Forewarning`, `NBT_ZAF_Last_Shipment_Date`, `NBT_ZAF_Notice`, `NBT_ZAF_Opening_Hours`, `NBT_ZAF_Outstandin_Orders`, `NBT_ZAF_PrintPriceWithoutDisc`, `NBT_ZAF_Reference_Person`, `NBT_ZAF_Sales_Accountable`, `NBT_ZAF_Sales_Channel`, `NBT_ZAF_Skip_RIBA_Charge`, `NBT_ZAF_Stat_CountryReg_Code`, `NBT_ZAF_Work_Description`, `NBTZAFIT_Amazon`, `NBTZAFIT_BRT_Note`, `NBTZAFIT_Contact_Name`, `NBTZAFIT_CrossRefCodiceTipoXML`, `NBTZAFIT_Export_Item_Coding`, `NBTZAFIT_Reason_Code_CONAI_FE`, `NBTZAFIT_DeliveryInstruction_1`, `NBTZAFIT_DeliveryInstruction_2`

**Campi filtro (non sono dati: filtrano la pagina)** (6)

`Global_Dimension_1_Filter`, `Global_Dimension_2_Filter`, `Currency_Filter`, `Date_Filter`, `Ship_to_Filter`, `Exposure_Filter`

### `Agenti` — 11 campi

- `Code` · String
- `Name` · String
- `Commission_Percent` · Decimal
- `Phone_No` · String
- `NBT_Salesperson_Type` · String
- `NBT_Salesp_Comm_Settl_G_L_Acc` · String
- `NBT_Salesp_Comm_Cost_G_L_Acc` · String
- `NBT_SimRcptToInv_G_L_Acc` · String
- `NBT_Commission_Vendor_No` · String
- `Privacy_Blocked` · Boolean
- `Coupled_to_Dataverse` · Boolean

### `Price_List` — 17 campi

- `Code` · String
- `Description` · String
- `SourceType` · String
- `JobSourceType` · String
- `AssignToParentNo` · String
- `SourceNo` · String
- `AssignToNo` · String
- `VATBusPostingGrPrice` · String
- `PriceIncludesVAT` · Boolean
- `AmountType` · String
- `Status` · String
- `CurrencyCode` · String
- `StartingDate` · Date
- `EndingDate` · Date
- `AllowUpdatingDefaults` · Boolean
- `AllowInvoiceDisc` · Boolean
- `AllowLineDisc` · Boolean

### `Price_ListLines` — 33 campi

- `Price_List_Code` · String
- `Line_No` · Int32
- `SourceType` · String
- `JobSourceType` · String
- `ParentSourceNo` · String
- `AssignToParentNo` · String
- `SourceNo` · String
- `AssignToNo` · String
- `NBT_ZAF_Status` · String
- `CurrencyCode` · String
- `StartingDate` · Date
- `EndingDate` · Date
- `Asset_Type` · String
- `Asset_No` · String
- `Product_No` · String
- `Description` · String
- `Variant_Code` · String
- `Variant_Code_Lookup` · String
- `Work_Type_Code` · String
- `Unit_of_Measure_Code` · String
- `Unit_of_Measure_Code_Lookup` · String
- `Minimum_Quantity` · Decimal
- `Amount_Type` · String
- `Unit_Price` · Decimal
- `Cost_Factor` · Decimal
- `Allow_Line_Disc` · Boolean
- `NBT_ZAF_Extra_Line_Discount` · String
- `Line_Discount_Percent` · Decimal
- `NBT_Line_Discount_Promotion` · Int32
- `NBT_Extra_Line_Discount` · String
- `Allow_Invoice_Disc` · Boolean
- `PriceIncludesVAT` · Boolean
- `VATBusPostingGrPrice` · String

### `Listini_prezzi_vendita_righe` — 33 campi

- `Price_List_Code` · String
- `Line_No` · Int32
- `SourceType` · String
- `JobSourceType` · String
- `ParentSourceNo` · String
- `AssignToParentNo` · String
- `SourceNo` · String
- `AssignToNo` · String
- `NBT_ZAF_Status` · String
- `CurrencyCode` · String
- `StartingDate` · Date
- `EndingDate` · Date
- `Asset_Type` · String
- `Asset_No` · String
- `Product_No` · String
- `Description` · String
- `Variant_Code` · String
- `Variant_Code_Lookup` · String
- `Work_Type_Code` · String
- `Unit_of_Measure_Code` · String
- `Unit_of_Measure_Code_Lookup` · String
- `Minimum_Quantity` · Decimal
- `Amount_Type` · String
- `Unit_Price` · Decimal
- `Cost_Factor` · Decimal
- `Allow_Line_Disc` · Boolean
- `NBT_ZAF_Extra_Line_Discount` · String
- `Line_Discount_Percent` · Decimal
- `NBT_Line_Discount_Promotion` · Int32
- `NBT_Extra_Line_Discount` · String
- `Allow_Invoice_Disc` · Boolean
- `PriceIncludesVAT` · Boolean
- `VATBusPostingGrPrice` · String

### `ListiniAcquisto_test` — 11 campi

- `Code` · String
- `Description` · String
- `Status` · String
- `Allow_Updating_Defaults` · Boolean
- `Defines` · String
- `Currency_Code` · String
- `SourceGroup` · String
- `SourceType` · String
- `SourceNo` · String
- `Starting_Date` · Date
- `Ending_Date` · Date

### `ListiniAcquisto_righe` — 16 campi

- `Code` · String
- `Description` · String
- `SourceType` · String
- `JobSourceType` · String
- `AssignToParentNo` · String
- `SourceNo` · String
- `AssignToNo` · String
- `PriceIncludesVAT` · Boolean
- `AmountType` · String
- `Status` · String
- `CurrencyCode` · String
- `StartingDate` · Date
- `EndingDate` · Date
- `AllowUpdatingDefaults` · Boolean
- `AllowInvoiceDisc` · Boolean
- `AllowLineDisc` · Boolean

### `ListiniAcquisto_righeLines` — 33 campi

- `Price_List_Code` · String
- `NBT_ZAF_Line_No` · Int32
- `SourceType` · String
- `JobSourceType` · String
- `ParentSourceNo` · String
- `AssignToParentNo` · String
- `SourceNo` · String
- `AssignToNo` · String
- `NBT_ZAF_AssignToName` · String
- `CurrencyCode` · String
- `StartingDate` · Date
- `EndingDate` · Date
- `Asset_Type` · String
- `Asset_No` · String
- `Product_No` · String
- `Description` · String
- `Variant_Code` · String
- `Variant_Code_Lookup` · String
- `Work_Type_Code` · String
- `Unit_of_Measure_Code` · String
- `Unit_of_Measure_Code_Lookup` · String
- `Minimum_Quantity` · Decimal
- `Amount_Type` · String
- `DirectUnitCost` · Decimal
- `Unit_Cost` · Decimal
- `Allow_Line_Disc` · Boolean
- `NBT_ZAF_Extra_Line_Discount` · String
- `Line_Discount_Percent` · Decimal
- `NBT_Line_Discount` · Int32
- `NBT_Extra_Line_Discount` · String
- `Allow_Invoice_Disc` · Boolean
- `PriceIncludesVAT` · Boolean
- `VATBusPostingGrPrice` · String

### `DB_Righe` — 23 campi

- `Production_BOM_No` · String
- `Version_Code` · String
- `Line_No` · Int32
- `Type` · String
- `No` · String
- `Variant_Code` · String
- `Description` · String
- `Calculation_Formula` · String
- `Length` · Decimal
- `Width` · Decimal
- `Depth` · Decimal
- `Weight` · Decimal
- `Quantity_per` · Decimal
- `Unit_of_Measure_Code` · String
- `Scrap_Percent` · Decimal
- `Routing_Link_Code` · String
- `CO2e_per_Unit` · Decimal
- `Position` · String
- `Position_2` · String
- `Position_3` · String
- `Lead_Time_Offset` · String
- `Starting_Date` · Date
- `Ending_Date` · Date

### `DBAssemblaggio` — 17 campi

- `Parent_Item_No` · String
- `Line_No` · Int32
- `Type` · String
- `No` · String
- `Variant_Code` · String
- `Description` · String
- `Assembly_BOM` · Boolean
- `NBT_ZAF_Component_Type` · String
- `Quantity_per` · Decimal
- `Unit_of_Measure_Code` · String
- `Installed_in_Item_No` · String
- `Position` · String
- `Position_2` · String
- `Position_3` · String
- `Machine_No` · String
- `Lead_Time_Offset` · String
- `Resource_Usage_Type` · String

### `RigheAnalisiVenduto` — 208 campi

**Campi Business Central standard** (186)

`Entry_No`, `Document_Template_Code`, `Document_Template_Description`, `Document_Type`, `Document_No`, `Line_No`, `Sell_to_Customer_No`, `Type`, `No`, `Location_Code`, `Description`, `Description_2`, `Unit_of_Measure`, `Quantity`, `Unit_Price`, `VAT_Percent`, `Line_Discount_Percent`, `Line_Discount_Amount`, `Amount`, `Amount_Including_VAT`, `Allow_Invoice_Disc`, `Shortcut_Dimension_1_Code`, `Shortcut_Dimension_2_Code`, `Quantity_Shipped`, `Quantity_Invoiced`, `Bill_to_Customer_No`, `Currency_Code`, `Line_Amount`, `Posting_Date`, `Posting_Date_Week`, `Document_Date`, `Document_Date_Week`, `Sorting_Month`, `Unit_of_Measure_Code`, `Item_Category_Code`, `Shipping_Agent_Code`, `Shipping_Agent_Service_Code`, `Bill_to_Name`, `Bill_to_Name_2`, `Bill_to_Address`, `Bill_to_Address_2`, `Bill_to_City`, `Bill_to_Post_Code`, `Bill_to_County`, `Bill_to_Country_Region_Code`, `Ship_to_Code`, `Ship_to_Name`, `Ship_to_Name_2`, `Ship_to_Address`, `Ship_to_Address_2`, `Ship_to_City`, `Ship_to_Post_Code`, `Ship_to_County`, `Ship_to_Country_Region_Code`, `Stat_CountryReg_Code`, `Payment_Method_Code`, `Payment_Method_Descr`, `Payment_Terms_Code`, `Payment_Terms_Descr`, `Shipment_Method_Code`, `Shipment_Method_Descr`, `Net_Weight`, `Gross_Weight`, `Volume`, `Salesperson_Code`, `Salesperson_Name`, `Salesperson_Code_2`, `Salesperson_Name_2`, `Packages`, `Pallet_No`, `Sales_Channel`, `Sales_Channel_Desciption`, `Customer_Category`, `Sales_Accountable`, `Subject_to_RAEE`, `Battery_Item`, `Finish`, `Variant`, `Style`, `Brand`, `Collection`, `Product_Type`, `Family`, `Novelty`, `To_Be_eliminated`, `Diameter`, `Side_1`, `Side_2`, `Partial_Height`, `Total_Height`, `Product_Finishing`, `Product_RAL`, `Product_Protrusion`, `Main_Material`, `Main_Processing`, `Empty_Code`, `Source`, `Source_Type`, `Total_Watt`, `Led_Source_Watt`, `Color_Temperature`, `Lamp_Lumens`, `Lumens_Light_Source`, `Chemical_Composition`, `Light_Band_Corner`, `IRC_CRI`, `Led_Power_Supply`, `Product_Code`, `Source_Code`, `Light_Sour_Energy_Cls`, `Driver_Code`, `Battery_Code`, `Supply_Voltage`, `Charger_Driver`, `Charger_Driver_INPUT`, `Charger_Driver_OUTPUT`, `Frequency`, `Class`, `Dimmable_Product`, `Dimmer_Type`, `Presence_Sensor`, `Light_Sensor`, `Lamp_Lifespan`, `Battery_Type`, `No_of_Battery_Package`, `Battery_Autonomy`, `Recharge`, `IP`, `IK`, `Salt_Spray_Resistance`, `Thermal_Dissipation`, `Usage`, `Usb_Type`, `Made_In`, `Product_Line`, `Led_Source_Watt_Sr_2`, `Color_Temperature_Sr_2`, `Lumens_Light_Source_S2`, `Light_Band_Corner_Sr_2`, `IRC_CRI_Source_2`, `Light_Sour_Ener_Cls_S2`, `Collection_2`, `Hole_instal_recessed`, `Product_Capacity_CL`, `OnPage_Qty_On_Package`, `Amount_LCY`, `Unit_Price_LCY`, `Line_Discount_Amount_LCY`, `Ordered_Amount_LCY`, `Invoiced_Amount_LCY`, `Outstanding_Quantity`, `Shipped_Value_LCY`, `Outstanding_Amount_LCY`, `Shpt_not_Invoiced_LCY`, `Item_Cat_Code_Description`, `Shipping_Agent_Description`, `Channel_Description`, `Cust_Category_Description`, `Product_Finishing_Description`, `Variant_Description`, `Style_Description`, `Brand_Description`, `Product_Type_Description`, `Family_Description`, `Product_RAL_Description`, `Main_Material_Description`, `Main_Processing_Description`, `Source_Description`, `Source_Type_Description`, `Product_Code_Description`, `Source_Code_Description`, `Driver_Code_Description`, `Battery_Code_Description`, `Charger_Driver_Description`, `Class_Description`, `Dimmable_Product_Description`, `Dimmer_Type_Description`, `Presence_Sensor_Description`, `Light_Sensor_Description`, `Battery_Type_Description`, `IP_Description`, `Thermal_Dissipation_Descr`, `Usage_Description`, `Territory_Name`, `Reason_Code`, `Reason_Description`

**Personalizzazioni partner (NBT_*)** (3)

`NBT_Free_Gift_Line`, `NBT_Free_Gift`, `NBT_Sell_to_Territory_Code`

**Personalizzazioni Zafferano (NBT_ZAF_*)** (1)

`NBT_ZAF_Transport_Cost`

**Imballo (tre livelli)** (18)

`Package_1_Net_Weight`, `Package_1_Gross_Weight`, `Package_1_Tare_Weight`, `Package_1_Measure_1`, `Package_1_Measure_2`, `Package_1_Measure_3`, `Package_2_Net_Weight`, `Package_2_Gross_Weight`, `Package_2_Tare_Weight`, `Package_2_Measure_1`, `Package_2_Measure_2`, `Package_2_Measure_3`, `Package_3_Net_Weight`, `Package_3_Gross_Weight`, `Package_3_Tare_Weight`, `Package_3_Measure_1`, `Package_3_Measure_2`, `Package_3_Measure_3`

### `Ordini_di_Vendita` — 216 campi

**Campi Business Central standard** (131)

`Document_Type`, `No`, `Sell_to_Customer_No`, `Sell_to_Customer_Name`, `Sell_to_Customer_Name_2`, `Quote_No`, `Posting_Description`, `Sell_to_Address`, `Sell_to_Address_2`, `Sell_to_City`, `Sell_to_County`, `Sell_to_Post_Code`, `Sell_to_Country_Region_Code`, `Sell_to_Contact_No`, `Sell_to_Phone_No`, `SellToMobilePhoneNo`, `Sell_to_E_Mail`, `Sell_to_Contact`, `No_of_Archived_Versions`, `Document_Date`, `Operation_Occurred_Date`, `Posting_Date`, `VAT_Reporting_Date`, `Order_Date`, `Due_Date`, `Requested_Delivery_Date`, `Promised_Delivery_Date`, `External_Document_No`, `Your_Reference`, `ShpfyOrderNo`, `ShpfyShopify_Risk_Level`, `Salesperson_Code`, `Campaign_No`, `Opportunity_No`, `Responsibility_Center`, `Assigned_User_ID`, `Operation_Type`, `Activity_Code`, `Job_Queue_Status`, `Status`, `WorkDescription`, `NBTFE_ProForma_Created`, `Currency_Code`, `Company_Bank_Account_Code`, `VAT_Country_Region_Code`, `VAT_Registration_No`, `Prices_Including_VAT`, `Gen_Bus_Posting_Group`, `VAT_Bus_Posting_Group`, `Customer_Posting_Group`, `Payment_Terms_Code`, `Payment_Method_Code`, `Bank_Account`, `Cumulative_Bank_Receipts`, `EU_3_Party_Trade`, `Fattura_Project_Code`, `Fattura_Tender_Code`, `Fattura_Document_Type`, `Fattura_Stamp`, `Fattura_Stamp_Amount`, `SelectedPayments`, `Shortcut_Dimension_1_Code`, `Shortcut_Dimension_2_Code`, `Journal_Templ_Name`, `Direct_Debit_Mandate_ID`, `_x0033_rd_Party_Loader_Type`, `_x0033_rd_Party_Loader_No`, `Customer_Purchase_Order_No`, `ShippingOptions`, `Ship_to_Code`, `Ship_to_Name`, `Ship_to_Name_2`, `Ship_to_Address`, `Ship_to_Address_2`, `Ship_to_City`, `Ship_to_County`, `Ship_to_Post_Code`, `Ship_to_Country_Region_Code`, `Additional_Information`, `Additional_Notes`, `Additional_Instructions`, `TDD_Prepared_By`, `Ship_to_Phone_No`, `Ship_to_Contact`, `Shipment_Method_Code`, `Shipping_Agent_Code`, `Shipping_Agent_Service_Code`, `BillToOptions`, `Bill_to_Name`, `Bill_to_Name_2`, `Bill_to_Address`, `Bill_to_Address_2`, `Bill_to_City`, `Bill_to_County`, `Bill_to_Post_Code`, `Bill_to_Country_Region_Code`, `Bill_to_Contact_No`, `Bill_to_Contact`, `BillToContactPhoneNo`, `BillToContactMobilePhoneNo`, `BillToContactEmail`, `Location_Code`, `Shipment_Date`, `Shipping_Advice`, `Outbound_Whse_Handling_Time`, `Shipping_Time`, `Late_Order_Shipping`, `Combine_Shipments`, `Completely_Shipped`, `Transaction_Specification`, `Transaction_Type`, `Transport_Method`, `Exit_Point`, `Area`, `Applicable_For_Serv_Decl`, `Service_Tariff_No`, `Language_Code`, `Format_Region`, `Prepayment_Percent`, `Compress_Prepayment`, `Prepmt_Payment_Terms_Code`, `Prepayment_Due_Date`, `Prepmt_Payment_Discount_Percent`, `Prepmt_Pmt_Discount_Date`, `Prepmt_CM_Refers_to_Period`, `Individual_Person`, `Resident`, `First_Name`, `Last_Name`, `Date_of_Birth`, `Fiscal_Code`

**Personalizzazioni partner (NBT_*)** (71)

`NBT_Invoice_Discount_Calculation`, `NBT_Invoice_Discount_Value`, `NBT_Sell_to_Territory_Code`, `NBT_Mail_Sent`, `NBT_CustomerPriority`, `NBT_Partial_and_Closed`, `NBT_Reference_Date`, `NBT_Yor_Reference_Date`, `NBT_Salesperson_Code_2`, `NBT_Internal_Salesperson`, `NBT_Reason1_Code`, `NBT_Shipment_Invoice`, `NBT_Without_Inventory`, `NBT_IT_TD_Code`, `NBT_Customer_Commission_Group`, `NBT_IT_Cust_Letter_of_Int_No`, `NBT_On_Hold`, `NBT_Payment_Bank`, `NBT_CIG_Code`, `NBT_CUP_code`, `NBT_CCC`, `NBT_IT_E_Invoice_Activity`, `NBT_ship_to_Territory_Code`, `NBT_ChargeShipping`, `NBT_bill_to_Territory_Code`, `NBT_No_Invoicing`, `NBT_Shipment_from`, `NBT_Start_Date`, `NBT_Start_Time`, `NBT_Appearance_of_the_goods`, `NBT_Packages`, `NBT_No_Pallet`, `NBT_Volume`, `NBT_License_Plate`, `NBT_Net_Weight`, `NBT_gross_Weight`, `NBT_Shipment_Amount`, `NBT_Duty_Amount`, `NBT_Prepayment_Percent`, `NBT_B2B_Order_Type`, `NBT_B2B_Ordered_By`, `NBT_B2B_Insert_Time`, `NBT_Code_1`, `NBT_Code_2`, `NBT_Code_3`, `NBT_Code_4`, `NBT_Code_5`, `NBT_Code_6`, `NBT_Code_7`, `NBT_Code_8`, `NBT_Code_9`, `NBT_Code_10`, `NBT_Text_1`, `NBT_Text_2`, `NBT_Text_3`, `NBT_Text_4`, `NBT_Text_5`, `NBT_Boolean_1`, `NBT_Boolean_2`, `NBT_Boolean_3`, `NBT_Boolean_4`, `NBT_Boolean_5`, `NBT_Integer_1`, `NBT_Integer_2`, `NBT_Integer_3`, `NBT_Integer_4`, `NBT_Decimal_1`, `NBT_Decimal_2`, `NBT_Date_1`, `NBT_Date_2`, `NBT_Date_3`

**Personalizzazioni Zafferano (NBT_ZAF_*)** (11)

`NBT_ZAF_B2B_Notes`, `NBT_ZAF_Stat_CountryReg_Code`, `NBT_ZAF_Shpfy_Order_No`, `NBT_ZAF_ASN_Amazon`, `NBT_ZAF_Mixed_Payment`, `NBT_ZAF_Special_Order`, `NBTZAFIT_BRT_Service_Type`, `NBTZAFIT_BRT_Note`, `NBTZAFIT_DeliveryInstruction_1`, `NBTZAFIT_DeliveryInstruction_2`, `NBT_ZAF_Prepayment`

**Imballo (tre livelli)** (1)

`Package_Tracking_No`

**Campi filtro (non sono dati: filtrano la pagina)** (2)

`Date_Filter`, `Location_Filter`

### `Ordini_di_VenditaSalesLines` — 187 campi

**Campi Business Central standard** (115)

`Document_Type`, `Document_No`, `Line_No`, `Type`, `FilteredTypeField`, `No`, `Service_Tariff_No`, `Item_Reference_No`, `ShpfyOrderNo`, `Include_in_VAT_Transac_Rep`, `IC_Partner_Code`, `IC_Partner_Ref_Type`, `Prepmt_CM_Refers_to_Period`, `IC_Partner_Reference`, `IC_Item_Reference`, `Variant_Code`, `Substitution_Available`, `Purchasing_Code`, `Nonstock`, `Gen_Bus_Posting_Group`, `Gen_Prod_Posting_Group`, `VAT_Bus_Posting_Group`, `VAT_Prod_Posting_Group`, `Description`, `Description_2`, `Drop_Shipment`, `Special_Order`, `Return_Reason_Code`, `Location_Code`, `Bin_Code`, `Sust_Account_No`, `Control50`, `Quantity`, `Qty_to_Assemble_to_Order`, `Reserved_Quantity`, `Unit_of_Measure_Code`, `Unit_of_Measure`, `Unit_Cost_LCY`, `SalesPriceExist`, `Unit_Price`, `Tax_Liable`, `Tax_Area_Code`, `Tax_Group_Code`, `Line_Discount_Percent`, `Line_Amount`, `Service_Commitments`, `Customer_Contract_No`, `Vendor_Contract_No`, `Allocation_Account_No`, `SalesLineDiscExists`, `Line_Discount_Amount`, `Prepayment_Percent`, `Prepmt_Line_Amount`, `Prepmt_Amt_Inv`, `Allow_Invoice_Disc`, `Inv_Discount_Amount`, `Inv_Disc_Amount_to_Invoice`, `Qty_to_Ship`, `Quantity_Shipped`, `Qty_to_Invoice`, `Quantity_Invoiced`, `Total_CO2e`, `Total_EPR_Fee`, `Prepmt_Amt_to_Deduct`, `Prepmt_Amt_Deducted`, `Allow_Item_Charge_Assignment`, `Qty_to_Assign`, `Service_Transaction_Type_Code`, `Applicable_For_Serv_Decl`, `Item_Charge_Qty_to_Handle`, `Qty_Assigned`, `Requested_Delivery_Date`, `Promised_Delivery_Date`, `Planned_Delivery_Date`, `Planned_Shipment_Date`, `Shipment_Date`, `Shipping_Agent_Code`, `Shipping_Agent_Service_Code`, `Shipping_Time`, `Work_Type_Code`, `Whse_Outstanding_Qty`, `Whse_Outstanding_Qty_Base`, `ATO_Whse_Outstanding_Qty`, `ATO_Whse_Outstd_Qty_Base`, `Outbound_Whse_Handling_Time`, `Blanket_Order_No`, `Blanket_Order_Line_No`, `FA_Posting_Date`, `Depr_until_FA_Posting_Date`, `Depreciation_Book_Code`, `Use_Duplication_List`, `Duplicate_in_Depreciation_Book`, `Appl_from_Item_Entry`, `Appl_to_Item_Entry`, `Deferral_Code`, `Shortcut_Dimension_1_Code`, `Shortcut_Dimension_2_Code`, `ShortcutDimCode3`, `ShortcutDimCode4`, `ShortcutDimCode5`, `ShortcutDimCode6`, `ShortcutDimCode7`, `ShortcutDimCode8`, `Gross_Weight`, `Net_Weight`, `Unit_Volume`, `Units_per_Parcel`, `Attached_to_Line_No`, `Attached_Lines_Count`, `TotalSalesLine_Line_Amount`, `Invoice_Discount_Amount`, `Invoice_Disc_Pct`, `Total_Amount_Excl_VAT`, `Total_VAT_Amount`, `Total_Amount_Incl_VAT`

**Personalizzazioni partner (NBT_*)** (55)

`NBT_IT_E_Invoice_Activity`, `NBT_IT_Cust_Letter_of_Int_No`, `NBT_Item_Commission_Group`, `NBT_Add_to_ProForma`, `NBT_Line_Discount_Promotion`, `NBT_Extra_Line_Discount`, `NBT_Free_Gift_Line`, `NBT_Free_Gift`, `NBT_Without_Inventory`, `NBT_Line_Closed`, `NBT_Original_Quantity`, `NBT_Tariff_No`, `NBT_Code_1`, `NBT_Code_2`, `NBT_Code_3`, `NBT_Code_4`, `NBT_Code_5`, `NBT_Code_6`, `NBT_Code_7`, `NBT_Code_8`, `NBT_Code_9`, `NBT_Code_10`, `NBT_Text_1`, `NBT_Text_2`, `NBT_Text_3`, `NBT_Text_4`, `NBT_Text_5`, `NBT_Boolean_1`, `NBT_Boolean_2`, `NBT_Boolean_3`, `NBT_Boolean_4`, `NBT_Boolean_5`, `NBT_Integer_1`, `NBT_Integer_2`, `NBT_Integer_3`, `NBT_Integer_4`, `NBT_Decimal_1`, `NBT_Decimal_2`, `NBT_Decimal_3`, `NBT_Date_1`, `NBT_Date_2`, `NBT_Date_3`, `NBT_VAT_Identifier`, `NBT_VAT_Bus_Posting_Group`, `NBT_PriceList_Code_Price`, `NBT_PriceList_Line_Price`, `NBT_PriceList_Code_Disc`, `NBT_PriceList_Line_Disc`, `NBT_IT_Exclude_CONAI_Charge`, `NBT_Accrual_Starting_Date`, `NBT_Accrual_Ending_Date`, `NBT_Accrual_Setup`, `NBT_Accrual_Period`, `NBT_Group_Bonus_Code`, `NBT_Bonus_Group`

**Personalizzazioni Zafferano (NBT_ZAF_*)** (16)

`NBT_ZAF_AutoPost`, `NBTZAFIT_Return_Reason_Code`, `NBTZAFIT_Return_Reason`, `NBTZAFIT_Return_Process_Min`, `NBT_ZAF_InTransitInv`, `NBT_ZAF_Applied_Sales_Order`, `NBT_ZAF_Appl_To_Sal_Ord_Line`, `NBT_ZAF_Order_Reason`, `NBT_ZAF_Transport_Cost`, `NBT_ZAF_Stat_CountryReg_Code`, `NBT_ZAF_Applied_Sales_Shipment`, `NBT_ZAF_Applied_To_Sales_Inv`, `NBT_ZAF_Recurring_Line`, `NBT_ZAF_NEW_Dashb_Res_Qty`, `NBT_ZAF_Pack_Linked_Line_No`, `NBT_ZAF_Campaign_No`

**Imballo (tre livelli)** (1)

`NBT_ZAF_Package_Note`

### `OC_testate` — 65 campi

**Campi Business Central standard** (49)

`Document_Type`, `No`, `ShpfyOrderNo`, `ShpfyRiskLevel`, `Sell_to_Customer_No`, `Sell_to_Customer_Name`, `External_Document_No`, `Sell_to_Post_Code`, `Sell_to_Country_Region_Code`, `Sell_to_Contact`, `Bill_to_Customer_No`, `Bill_to_Name`, `Bill_to_Post_Code`, `Bill_to_Country_Region_Code`, `Bill_to_Contact`, `Ship_to_Code`, `Ship_to_Name`, `Ship_to_Post_Code`, `Ship_to_Country_Region_Code`, `Ship_to_Contact`, `Posting_Date`, `Shortcut_Dimension_1_Code`, `Shortcut_Dimension_2_Code`, `Location_Code`, `Quote_No`, `Salesperson_Code`, `Assigned_User_ID`, `Currency_Code`, `Document_Date`, `Requested_Delivery_Date`, `Campaign_No`, `Status`, `Payment_Terms_Code`, `Due_Date`, `Payment_Discount_Percent`, `Shipment_Method_Code`, `Shipping_Agent_Code`, `Shipping_Agent_Service_Code`, `Shipment_Date`, `Shipping_Advice`, `Completely_Shipped`, `Job_Queue_Status`, `Amt_Ship_Not_Inv_LCY_Base`, `Amt_Ship_Not_Inv_LCY`, `Amount`, `Amount_Including_VAT`, `Posting_Description`, `Your_Reference`, `Coupled_to_Dataverse`

**Personalizzazioni partner (NBT_*)** (5)

`NBT_Document_Template_Code`, `NBT_MDW_Status_Code`, `NBT_Mail_Sent`, `NBT_Prepayment_Percent`, `NBT_B2B_Order_Type`

**Personalizzazioni Zafferano (NBT_ZAF_*)** (9)

`NBT_ZAF_TemplateDescription`, `NBT_ZAF_Stat_CountryReg_Code`, `NBT_ZAF_Reason_Code`, `NBT_ZAF_City`, `NBT_ZAF_Internal_Salesperson`, `NBT_ZAF_ASN_Amazon`, `NBT_ZAF_Payment_Method_Code`, `NBT_ZAF_Prepayment`, `NBT_ZAF_Special_Order`

**Imballo (tre livelli)** (1)

`Package_Tracking_No`

**Campi filtro (non sono dati: filtrano la pagina)** (1)

`Location_Filter`

### `ItemLedgerEntries` — 30 campi

- `Entry_No` · Int32
- `Entry_Type` · String
- `Item_No` · String
- `Item_Reference_No` · String
- `Lot_No` · String
- `Item_Category_Code` · String
- `Posting_Date` · Date
- `Expiration_Date` · Date
- `Warranty_Date` · Date
- `Document_Date` · Date
- `Document_No` · String
- `Document_Type` · String
- `Location_Code` · String
- `Job_No` · String
- `Job_Task_No` · String
- `Open` · Boolean
- `Quantity` · Decimal
- `Unit_of_Measure_Code` · String
- `Qty_per_Unit_of_Measure` · Decimal
- `Remaining_Quantity` · Decimal
- `Invoiced_Quantity` · Decimal
- `Dimension_Set_ID` · Int32
- `Cost_Amount_Expected` · Decimal
- `Cost_Amount_Actual` · Decimal
- `Cost_Amount_Non_Invtbl` · Decimal
- `Purchase_Amount_Expected` · Decimal
- `Purchase_Amount_Actual` · Decimal
- `Sales_Amount_Expected` · Decimal
- `Sales_Amount_Actual` · Decimal
- `Item_Description` · String

### `Ubicazioni` — 2 campi

- `Code` · String
- `Name` · String

### `Collocazioni` — 18 campi

- `Location_Code` · String
- `Code` · String
- `Zone_Code` · String
- `Description` · String
- `Bin_Type_Code` · String
- `Warehouse_Class_Code` · String
- `Block_Movement` · String
- `Special_Equipment_Code` · String
- `Bin_Ranking` · Int32
- `Maximum_Cubage` · Decimal
- `Maximum_Weight` · Decimal
- `Empty` · Boolean
- `Cross_Dock_Bin` · Boolean
- `Dedicated` · Boolean
- `NBT_ZAF_Coin_Code` · String
- `NBT_ZAF_In_Transit_Bin` · Boolean
- `NBT_ZAF_No_of_Minimum_Pieces` · Int32
- `NBT_ZAF_Exlcude_from_Refiling` · Boolean

### `UM` — 4 campi

- `Code` · String
- `Description` · String
- `International_Standard_Code` · String
- `Coupled_to_Dataverse` · Boolean

### `Articoli_Statistici` — 2 campi

- `Code` · String
- `Description` · String
