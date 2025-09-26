/**
 * Review Data Module - Manages data collection from websocket events
 */
export default function createReviewDataModule(
  socket,
  UIModule,
  RecordingModule,
  GrievanceModule
) {
  return {
    // Use getter/setter for reviewData to access global data
    get reviewData() {
      return window.reviewData || {};
    },
    set reviewData(value) {
      window.reviewData = value;
    },

    editedData: {}, // Store user-edited versions
    taskCompletionStatus: {},
    firstSuccessTime: null,
    summaryTimer: null,
    updateTimer: null,
    isCollectingData: false,

    // Field mapping: websocket field name -> review element ID
    fieldMapping: {
      grievance_description: "grievanceDetailsReview",
      grievance_summary: "grievanceSummaryReview",
      grievance_categories: "grievanceCategoriesReview",
      complainant_full_name: "userNameReview",
      complainant_phone: "userPhoneReview",
      complainant_municipality: "userMunicipalityReview",
      complainant_village: "userVillageReview",
      complainant_address: "userAddressReview",
    },

    init: function () {
      // Listen for task completion events
      socket.on(
        "status_update:llm_processor",
        this.handleTaskCompletion.bind(this)
      );
      socket.on("status_update", this.handleTaskCompletion.bind(this));
      socket.on(
        "status_update:grievance",
        this.handleTaskCompletion.bind(this)
      );
      socket.on("status_update:user", this.handleTaskCompletion.bind(this));

      // Set up text editing functionality
      this.setupTextEditing();

      // Set up validation checkboxes
      this.setupValidationCheckboxes();

      // Hide re-record buttons
      this.hideRerecordButtons();

      // TEMPORARY: Add global reference for debugging
      window.debugReviewData = this;
      console.log(
        "[ReviewData] Module initialized - access via window.debugReviewData"
      );
    },

    hideRerecordButtons: function () {
      // Hide all re-record buttons (multiple selectors to catch all variations)
      const selectors = [
        'button[data-action="rerecord"]',
        ".rerecord-btn",
        'button:contains("Re-record")',
        'button:contains("🎤")',
      ];

      selectors.forEach((selector) => {
        try {
          const buttons = document.querySelectorAll(selector);
          buttons.forEach((btn) => {
            btn.style.display = "none";
            console.log("[ReviewData] Hid re-record button:", btn);
          });
        } catch (e) {
          // Some selectors might not work, ignore errors
        }
      });

      // Also look for buttons containing re-record text
      const allButtons = document.querySelectorAll("button");
      allButtons.forEach((btn) => {
        const text = btn.textContent.toLowerCase();
        if (text.includes("re-record") || text.includes("🎤")) {
          btn.style.display = "none";
          console.log("[ReviewData] Hid re-record button by text:", btn);
        }
      });
    },

    setupTextEditing: function () {
      // Handle Edit Text buttons
      document.addEventListener("click", (e) => {
        if (e.target.classList.contains("edit-text-btn")) {
          const fieldName = e.target.dataset.field;
          this.showEditArea(fieldName);
        }

        // Handle Save buttons
        if (e.target.classList.contains("save-btn")) {
          const fieldName = e.target.dataset.field;
          this.saveEditedText(fieldName);
        }

        // Handle Cancel buttons
        if (e.target.classList.contains("cancel-btn")) {
          const fieldName = e.target.dataset.field;
          this.cancelEdit(fieldName);
        }

        // Handle Delete All buttons
        if (e.target.classList.contains("delete-all-btn")) {
          const fieldName = e.target.dataset.field;
          this.deleteAllText(fieldName);
        }

        // Handle Modify Categories button
        if (
          e.target.textContent.includes("Modify Categories") ||
          e.target.classList.contains("modify-categories-btn")
        ) {
          this.showCategoryDropdown();
        }
      });
    },

    setupValidationCheckboxes: function () {
      // Handle validation checkbox changes
      document.addEventListener("change", (e) => {
        if (e.target.type === "checkbox" && e.target.id.includes("Validated")) {
          const fieldName = e.target.id.replace("Validated", "");
          this.handleValidationChange(fieldName, e.target.checked);
        }
      });
    },

    showEditArea: function (fieldName) {
      const editAreaId = this.getEditAreaId(fieldName);
      const editArea = document.getElementById(editAreaId);
      const textareaId = this.getTextareaId(fieldName);
      const textarea = document.getElementById(textareaId);

      if (editArea && textarea) {
        // Get current text (edited version if exists, otherwise original)
        const currentText =
          this.editedData[fieldName] || this.reviewData[fieldName] || "";
        textarea.value = currentText;
        editArea.hidden = false;
        editArea.style.display = "block";
        textarea.focus();

        // Add Delete All button if it doesn't exist
        this.ensureDeleteAllButton(editAreaId, fieldName);
      }
    },

    ensureDeleteAllButton: function (editAreaId, fieldName) {
      const editArea = document.getElementById(editAreaId);
      const existingDeleteBtn = editArea.querySelector(".delete-all-btn");

      if (!existingDeleteBtn && editArea) {
        // Find the button container (where Save and Cancel buttons are)
        const buttonContainer = editArea.querySelector(".edit-buttons");
        if (buttonContainer) {
          // Create Delete All button
          const deleteBtn = document.createElement("button");
          deleteBtn.type = "button";
          deleteBtn.className = "delete-all-btn";
          deleteBtn.dataset.field = fieldName;
          deleteBtn.innerHTML = "🗑️ Delete All";
          deleteBtn.style.backgroundColor = "var(--error-color)";
          deleteBtn.style.color = "var(--text-color)";
          deleteBtn.style.border = "none";
          deleteBtn.style.padding = "8px 16px";
          deleteBtn.style.borderRadius = "4px";
          deleteBtn.style.marginLeft = "8px";
          deleteBtn.style.cursor = "pointer";

          // Insert before the Cancel button
          const cancelBtn = buttonContainer.querySelector(".cancel-btn");
          if (cancelBtn) {
            buttonContainer.insertBefore(deleteBtn, cancelBtn);
          } else {
            buttonContainer.appendChild(deleteBtn);
          }
        }
      }
    },

    saveEditedText: function (fieldName) {
      const textareaId = this.getTextareaId(fieldName);
      const textarea = document.getElementById(textareaId);
      const reviewElementId = this.fieldMapping[fieldName];
      const reviewElement = document.getElementById(reviewElementId);

      if (textarea && reviewElement) {
        const editedText = textarea.value.trim();
        // Store the edited version
        this.editedData[fieldName] = editedText;
        // Update reviewData immediately
        this.reviewData[fieldName] = editedText;
        // Update the display with edited text
        reviewElement.textContent = editedText;
        // Hide edit area
        this.hideEditArea(fieldName);
        console.log(
          `[ReviewData] Saved edited text for ${fieldName}: ${editedText}`
        );
      }
    },

    cancelEdit: function (fieldName) {
      this.hideEditArea(fieldName);
    },

    hideEditArea: function (fieldName) {
      const editAreaId = this.getEditAreaId(fieldName);
      const editArea = document.getElementById(editAreaId);
      if (editArea) {
        editArea.hidden = true;
      }
    },

    getEditAreaId: function (fieldName) {
      const mapping = {
        grievance_description: "grievanceDetailsEditArea",
        grievance_summary: "grievanceSummaryEditArea",
        complainant_full_name: "userNameEditArea",
        complainant_phone: "userPhoneEditArea",
        complainant_municipality: "userMunicipalityEditArea",
        complainant_village: "userVillageEditArea",
        complainant_address: "userAddressEditArea",
      };
      return mapping[fieldName];
    },

    getTextareaId: function (fieldName) {
      const mapping = {
        grievance_description: "grievanceDetailsEdit",
        grievance_summary: "grievanceSummaryEdit",
        complainant_full_name: "userNameEdit",
        complainant_phone: "userPhoneEdit",
        complainant_municipality: "userMunicipalityEdit",
        complainant_village: "userVillageEdit",
        complainant_address: "userAddressEdit",
      };
      return mapping[fieldName];
    },

    handleValidationChange: function (fieldName, isChecked) {
      // Find the corresponding h4 element and add/remove checkmark
      const reviewSections = document.querySelectorAll(".review-section");
      reviewSections.forEach((section) => {
        const h4 = section.querySelector("h4");
        const checkbox = section.querySelector(`#${fieldName}Validated`);

        if (checkbox && h4) {
          // Remove existing checkmark
          const existingCheckmark = h4.querySelector(".validated");
          if (existingCheckmark) {
            existingCheckmark.remove();
          }

          // Add checkmark if validated
          if (isChecked) {
            const checkmark = document.createElement("span");
            checkmark.className = "validated";
            checkmark.textContent = " ✅";
            h4.appendChild(checkmark);
          }
        }
      });

      console.log(`[ReviewData] Field ${fieldName} validation: ${isChecked}`);
    },

    handleTaskCompletion: function (data) {
      console.log("[ReviewData] Received task completion:", data);

      if (data.status === "SUCCESS" && data.message) {
        const result = data.message;

        // Start timer logic on first success
        if (!this.isCollectingData) {
          this.startDataCollection();
        }

        // Store the result data
        this.storeTaskResult(result);

        // Update UI immediately for responsiveness
        this.updateReviewUI(result);

        // Check if we can enable navigation
        this.checkNavigationStatus();
      }
    },

    startDataCollection: function () {
      console.log("[ReviewData] Starting data collection with 3-second timer");
      this.isCollectingData = true;
      this.firstSuccessTime = Date.now();

      // Set 3-second timer for summary
      this.summaryTimer = setTimeout(() => {
        this.sendSummaryUpdate();
        this.startPeriodicUpdates();
      }, 3000);
    },

    storeTaskResult: function (result) {
      console.log("[ReviewData] Processing result:", result);

      // Handle the new simplified structure
      let extractedData = {};

      // NEW: Handle direct result structure (from simplified websocket format)
      Object.entries(result).forEach(([key, value]) => {
        if (this.fieldMapping[key]) {
          extractedData[key] = value;
          console.log(`[ReviewData] Extracted directly: ${key} = ${value}`);
        }
      });

      // NEW: Handle the simplified values structure (for backward compatibility)
      if (result.values && typeof result.values === "object") {
        Object.entries(result.values).forEach(([key, value]) => {
          if (key !== "field_name" && this.fieldMapping[key]) {
            extractedData[key] = value;
            console.log(
              `[ReviewData] Extracted from values: ${key} = ${value}`
            );
          }
        });
      }

      // FALLBACK: Handle old nested structure (backward compatibility)
      if (result.value && typeof result.value === "object") {
        Object.entries(result.value).forEach(([key, value]) => {
          if (key !== "field_name" && this.fieldMapping[key]) {
            extractedData[key] = value;
            console.log(
              `[ReviewData] Extracted from nested value: ${key} = ${value}`
            );
          }
        });

        // Handle categories specially (they come as an array)
        if (result.value.grievance_categories) {
          extractedData.grievance_categories =
            result.value.grievance_categories;
        }
        if (result.value.grievance_summary) {
          extractedData.grievance_summary = result.value.grievance_summary;
        }
      }

      // Store the extracted data in global reviewData
      Object.entries(extractedData).forEach(([key, value]) => {
        window.reviewData[key] = value;
        this.taskCompletionStatus[key] = "completed";
        console.log(`[ReviewData] Stored ${key}: ${value}`);
      });
      console.log(
        "[DEBUG] window.reviewData after storeTaskResult:",
        window.reviewData
      );
      if (window.reviewData && Object.keys(window.reviewData).length > 0) {
        localStorage.setItem("reviewData", JSON.stringify(window.reviewData));
        console.log(
          "[DEBUG] Auto-saved reviewData to localStorage:",
          window.reviewData
        );
      }
    },

    updateReviewUI: function (result) {
      console.log(
        "[ReviewData] Updating UI with stored data:",
        this.reviewData
      );

      // Use the data we've already extracted and stored
      Object.entries(this.reviewData).forEach(([fieldName, fieldValue]) => {
        const elementId = this.fieldMapping[fieldName];
        if (elementId) {
          const element = document.getElementById(elementId);
          if (element) {
            // Only update if user hasn't edited this field
            if (!this.editedData[fieldName]) {
              if (
                fieldName === "grievance_categories" &&
                Array.isArray(fieldValue)
              ) {
                // Handle categories as a list
                element.innerHTML = fieldValue
                  .map((cat) => `<span class="category-tag">${cat}</span>`)
                  .join(" ");
              } else {
                element.textContent = fieldValue || "";
              }
              console.log(
                `[ReviewData] Updated UI element ${elementId} with: ${fieldValue}`
              );
            } else {
              console.log(
                `[ReviewData] Skipped updating ${elementId} - user has edited this field`
              );
            }
          }
        }
      });
    },

    checkNavigationStatus: function () {
      // Check if we have at least one contact_info or classification task completed
      const hasContactInfo = [
        "complainant_full_name",
        "complainant_phone",
        "complainant_municipality",
        "complainant_village",
        "complainant_address",
      ].some((field) => this.taskCompletionStatus[field] === "completed");

      const hasClassification = [
        "grievance_summary",
        "grievance_categories",
      ].some((field) => this.taskCompletionStatus[field] === "completed");

      if (hasContactInfo || hasClassification) {
        this.enableReviewNavigation();
      }
    },

    enableReviewNavigation: function () {
      const { step, window } = UIModule.getCurrentWindow();
      if (step === "attachments") {
        const nextBtn = document.querySelector(
          '#attachments-attachments .nav-btn[data-action="next"]'
        );
        if (nextBtn) {
          nextBtn.disabled = false;
          nextBtn.style.display = "";
          console.log("[ReviewData] Enabled navigation to review step");

          // Update button states
          UIModule.updateButtonStates({
            isRecording: RecordingModule.isRecording,
            hasRecording: RecordingModule.hasAnyRecording(),
            isSubmitting: GrievanceModule.isSubmitting,
          });
        }
      }
    },

    sendSummaryUpdate: function () {
      console.log("[ReviewData] Sending summary update after 3 seconds");
      console.log("[ReviewData] Collected data:", this.reviewData);
      console.log("[ReviewData] Edited data:", this.editedData);
      console.log("[ReviewData] Task status:", this.taskCompletionStatus);

      // Emit custom event for other modules
      window.dispatchEvent(
        new CustomEvent("reviewDataReady", {
          detail: {
            data: this.reviewData,
            editedData: this.editedData,
            completionStatus: this.taskCompletionStatus,
            timestamp: Date.now(),
          },
        })
      );
    },

    startPeriodicUpdates: function () {
      console.log(
        "[ReviewData] Starting periodic 1-second updates for new arrivals"
      );
      this.updateTimer = setInterval(() => {
        // Check if we have new data since last update
        // For now, just log - could add more sophisticated change detection
        console.log("[ReviewData] Periodic update check");
      }, 1000);
    },

    stopDataCollection: function () {
      if (this.summaryTimer) {
        clearTimeout(this.summaryTimer);
        this.summaryTimer = null;
      }
      if (this.updateTimer) {
        clearInterval(this.updateTimer);
        this.updateTimer = null;
      }
      this.isCollectingData = false;
      console.log("[ReviewData] Stopped data collection");
    },

    // Public method to get current review data (including user edits)
    getReviewData: function () {
      return {
        data: this.reviewData,
        editedData: this.editedData,
        completionStatus: this.taskCompletionStatus,
      };
    },

    // Public method to reset data (for new grievance)
    reset: function () {
      window.reviewData = {
        grievance_description: "",
        grievance_summary: "",
        grievance_categories: [],
        complainant_full_name: "",
        complainant_phone: "",
        complainant_municipality: "",
        complainant_village: "",
        complainant_address: "",
      };
      this.editedData = {};
      this.taskCompletionStatus = {};
      this.stopDataCollection();
      console.log("[ReviewData] Reset review data");
    },

    deleteAllText: function (fieldName) {
      const textareaId = this.getTextareaId(fieldName);
      const textarea = document.getElementById(textareaId);

      if (textarea) {
        // Clear the textarea
        textarea.value = "";
        textarea.focus();
        console.log(`[ReviewData] Cleared all text for ${fieldName}`);
      }
    },

    showCategoryDropdown: function () {
      // Get available categories
      this.loadCategories()
        .then((categories) => {
          this.createCategoryDropdown(categories);
        })
        .catch((error) => {
          console.error("[ReviewData] Error loading categories:", error);
          alert("Failed to load categories. Please try again.");
        });
    },

    loadCategories: function () {
      // For now, use hardcoded categories based on the lookup file
      // Later this could be an API call
      const categories = [
        "Cultural, Social - Cultural Site Disturbances",
        "Destruction Of Agrarian Resources - Crop Destruction",
        "Destruction Of Agrarian Resources - Destruction Of Agrarian Soils",
        "Destruction Of Agrarian Resources - Soil Pollution",
        "Economic, Social - Employment Opportunities",
        "Economic, Social - Land Acquisition Issues",
        "Environmental - Air Pollution",
        "Environmental - Drainage And Sewage Management",
        "Environmental - Noise Pollution",
        "Environmental, Social - Cutting Of Trees",
        "Gender - Gender Discrimination And Harrassment",
        "Gender, Social - Gender-Based Access Issues",
        "Malicious Behavior - Theft Of Crops",
        "Malicious Behavior - Theft Of Tools Or Equipment",
        "Malicious Behavior, Environmental - Fire Incidents",
        "Relocation Issues - Forced Relocation Issues",
        "Relocation Issues - Lack Of Infrastructure Of The Resettlement Site",
        "Relocation Issues - Poor Housing Quality Of The Resettlement Site",
        "Relocation Issues - Poor Location Of The Resettlement Site",
        "Relocation Of Public Utilities - Access To Electricity",
        "Relocation Of Public Utilities - Access To Water",
        "Safety - Road Safety Provisions",
        "Wildlife, Environmental - Wildlife Destruction",
        "Wildlife, Environmental - Wildlife Passage",
      ];

      return Promise.resolve(categories);
    },

    createCategoryDropdown: function (categories) {
      // Find the categories review section
      const categoryElement = document.getElementById(
        "grievanceCategoriesReview"
      );
      if (!categoryElement) {
        console.error("[ReviewData] Categories review element not found");
        return;
      }

      // Get current category (single selection)
      const currentCategories =
        this.editedData.grievance_categories ||
        this.reviewData.grievance_categories ||
        [];
      const currentCategory = Array.isArray(currentCategories)
        ? currentCategories[0]
        : currentCategories;

      // Create a container for the dropdown
      let dropdownContainer = document.getElementById(
        "categoryDropdownContainer"
      );
      if (!dropdownContainer) {
        dropdownContainer = document.createElement("div");
        dropdownContainer.id = "categoryDropdownContainer";
        dropdownContainer.style.cssText = `
                    margin: 15px 0;
                    padding: 15px;
                    border: 1px solid var(--border-color);
                    border-radius: var(--border-radius);
                    background-color: var(--dark-bg);
                `;

        // Insert after the categories review element
        categoryElement.parentNode.insertBefore(
          dropdownContainer,
          categoryElement.nextSibling
        );
      }

      // Create the dropdown content
      dropdownContainer.innerHTML = `
                <h4 style="margin-top: 0; color: var(--primary-color);">Select Grievance Category:</h4>
                <p style="color: var(--text-muted); margin-bottom: 15px; font-size: 0.9rem;">
                    Choose the category that best describes your grievance:
                </p>
                <div style="margin-bottom: 15px;">
                    <select id="categorySelect" aria-label="Select grievance category" style="
                        width: 100%;
                        padding: 8px 12px;
                        border: 1px solid var(--border-color);
                        border-radius: var(--border-radius);
                        font-size: 1rem;
                        background-color: var(--light-bg);
                        color: var(--text-color);
                    ">
                        <option value="">Select a category</option>
                        ${categories
                          .map(
                            (category) => `
                            <option value="${category}" ${
                              currentCategory === category ? "selected" : ""
                            }>${category}</option>
                        `
                          )
                          .join("")}
                    </select>
                </div>
                <div style="text-align: right;">
                    <button onclick="window.ReviewDataModule.applyCategorySelection()" 
                            style="padding: 10px 20px; background: var(--success-color); color: var(--text-color); border: none; border-radius: var(--border-radius); cursor: pointer;">
                        Apply Selected Category
                    </button>
                    <button onclick="window.ReviewDataModule.cancelCategorySelection()" 
                            style="padding: 10px 20px; background: var(--text-muted); color: var(--text-color); border: none; border-radius: var(--border-radius); cursor: pointer; margin-left: 10px;">
                        Cancel
                    </button>
                </div>
            `;

      console.log(
        "[ReviewData] Created category dropdown with",
        categories.length,
        "categories"
      );
    },

    handleCategoryChange: function () {
      // No longer needed with single select dropdown
    },

    applyCategorySelection: function () {
      const categorySelect = document.getElementById("categorySelect");
      if (!categorySelect) return;

      const selectedCategory = categorySelect.value;

      if (!selectedCategory) {
        alert("Please select a category.");
        return;
      }

      // Store the selected category as a single item (convert to array for compatibility)
      this.editedData.grievance_categories = [selectedCategory];

      // Update the UI display
      this.updateCategoryDisplay([selectedCategory]);

      // Hide the dropdown
      this.hideCategoryDropdown();

      console.log("[ReviewData] Applied category:", selectedCategory);
    },

    cancelCategorySelection: function () {
      this.hideCategoryDropdown();
    },

    hideCategoryDropdown: function () {
      const dropdownContainer = document.getElementById(
        "categoryDropdownContainer"
      );
      if (dropdownContainer) {
        dropdownContainer.remove();
      }
    },

    updateCategoryDisplay: function (categories) {
      const categoryElement = document.getElementById(
        "grievanceCategoriesReview"
      );
      if (categoryElement) {
        // Update the display with selected categories
        categoryElement.innerHTML = categories
          .map((cat) => `<span class="category-tag">${cat}</span>`)
          .join(" ");

        console.log("[ReviewData] Updated category display with:", categories);
      }
    },
  };
}
