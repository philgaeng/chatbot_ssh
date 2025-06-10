// Configuration
const CONFIG = {
  API_TOKEN: PropertiesService.getScriptProperties().getProperty('API_TOKEN'),
  BASE_URL: PropertiesService.getScriptProperties().getProperty('BASE_URL') || 'https://nepal-gms-chatbot.facets-ai.com/accessible-api'
};

// Function to fetch and populate data
function fetchAndPopulateData() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  
  // Clear existing data except header
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, 12).clear();
  }

  const options = {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${CONFIG.API_TOKEN}`,
      "Content-Type": "application/json"
    },
    muteHttpExceptions: true  // This will prevent the script from failing on HTTP errors
  };

  try {
    const response = UrlFetchApp.fetch(`${CONFIG.BASE_URL}/gsheet-get-grievances`, options);
    const responseCode = response.getResponseCode();
    const rawResponse = response.getContentText();
    Logger.log("[DEBUG] Response code: " + responseCode);
    Logger.log("[DEBUG] Raw response: " + rawResponse);
    
    if (responseCode === 200) {
      const data = JSON.parse(rawResponse);
      
      if (data.status === "success" && data.data.data.length > 0) {
        // Prepare data for sheet
        const values = data.data.data.map(grievance => [
          grievance.user_id,
          grievance.grievance_id,
          grievance.user_full_name,
          grievance.user_contact_phone,
          grievance.user_municipality,
          grievance.user_village,
          grievance.user_address,
          grievance.grievance_details,
          grievance.grievance_summary,
          grievance.grievance_categories,
          grievance.grievance_creation_date,
          grievance.status
        ]);

        // Write data to sheet starting from row 2 (after header)
        sheet.getRange(2, 1, values.length, 12).setValues(values);
        
        // Show success message
        SpreadsheetApp.getActiveSpreadsheet().toast('Data refreshed successfully!', 'Success');
      } else {
        SpreadsheetApp.getActiveSpreadsheet().toast('No data available', 'Info');
      }
    } else {
      Logger.log("[DEBUG] Error response: " + rawResponse);
      const errorData = JSON.parse(rawResponse);
      SpreadsheetApp.getActiveSpreadsheet().toast(`Error: ${errorData.message || 'Failed to fetch data'}`, 'Error');
    }
  } catch (err) {
    SpreadsheetApp.getActiveSpreadsheet().toast(`Error: ${err.message}`, 'Error');
    Logger.log("[DEBUG] Error fetching data: " + err.message);
  }
}

// Function to set up configuration
function setupConfig() {
  const ui = SpreadsheetApp.getUi();
  
  // Prompt for API token
  const tokenResponse = ui.prompt(
    'Setup Configuration',
    'Please enter your API token:',
    ui.ButtonSet.OK_CANCEL
  );
  
  if (tokenResponse.getSelectedButton() == ui.Button.OK) {
    const token = tokenResponse.getResponseText();
    PropertiesService.getScriptProperties().setProperty('API_TOKEN', token);
  }
  
  // Prompt for base URL with default value
  const urlResponse = ui.prompt(
    'Setup Configuration',
    'Please enter your API base URL (default: https://nepal-gms-chatbot.facets-ai.com/accessible-api):',
    ui.ButtonSet.OK_CANCEL
  );
  
  if (urlResponse.getSelectedButton() == ui.Button.OK) {
    const url = urlResponse.getResponseText() || 'https://nepal-gms-chatbot.facets-ai.com/accessible-api';
    PropertiesService.getScriptProperties().setProperty('BASE_URL', url);
  }
  
  ui.alert('Configuration saved successfully!');
}

// Function to set up the sheet
function setupSheet() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  
  // Set up headers
  const headers = [
    "User ID",
    "Grievance ID",
    "Full Name",
    "Contact Phone",
    "Municipality",
    "Village",
    "Address",
    "Grievance Details",
    "Summary",
    "Categories",
    "Creation Date",
    "Status"
  ];
  
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");

  // Add menu items
  SpreadsheetApp.getUi()
    .createMenu('Nepal Chatbot')
    .addItem('Refresh Data', 'fetchAndPopulateData')
    .addItem('Setup Configuration', 'setupConfig')
    .addToUi();
 }  



// Function to run on sheet open
function onOpen() {
  
  setupSheet();
  // Check if configuration exists
  if (!PropertiesService.getScriptProperties().getProperty('API_TOKEN')) {
    setupConfig();
  }
  fetchAndPopulateData();
}

// Function to refresh data periodically (can be set up as a trigger)
function refreshData() {
  fetchAndPopulateData();
}

function testDataRefresh() {
  try {
    fetchAndPopulateData();
    Logger.log("Refresh completed - check the sheet for data");
  } catch (error) {
    Logger.log("Error during refresh: " + error.toString());
  }
}

function checkProperties() {
  const scriptProperties = PropertiesService.getScriptProperties();
  const apiToken = scriptProperties.getProperty('API_TOKEN');
  const baseUrl = scriptProperties.getProperty('BASE_URL');
  
  Logger.log('API Token:', apiToken);
  Logger.log('Base URL:', baseUrl);
}