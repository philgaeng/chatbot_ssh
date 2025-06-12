# Ticketing System Functional Specifications

## 1. Core Functionality

### 1.1 Ticket Creation
- **Source**: 
  - Chatbot (Rasa)
  - Web Interface
  - API
  - Whatsapp
  - Facebook (Rasa)

- **Required Information**:
  - Grievance ID (auto-generated)
  - User Information
    - User ID (auto-generated)
    - Phone Number
    - Name
    - Location (Province/District/Municipality/Village/Address)
    - Email (optional)
  - Project Information
    - Provided by the QR code (Project Number)
  - Grievance Details
    - Grievance Details
    - Grievance Summary (AI generated)
    - Grievance Categories (AI generated)
  - Priority Level
    - Assigned by ticketing systems as per Category
  - Attachments (if any)

### 1.2 Ticket Lifecycle
1. **Status Flow**:
   ```
   New → In Progress → Escalated (optional) -> Resolved → Closed
   ```
   - New: Ticket created by chatbot or other channel
   - In progress: after verification of the info provided with the grievance, the OIC marks the ticket as in progress
   - Escalated: if escalated, the status is automatically changed to in progress in order to easily seggregate the tickets
   - Resolved: A resolution is found with the plaintiff - the status is changed by the OIC of the corresponding level
   - Closed: The resolution is considered accepted if either:
     - The user explicitly accepts it through available channels (Chatbot, Whatsapp)
     - No response is received after 7 days
     If the resolution is refused through any channel (digital, in-person, phone), the status returns to escalated.

   - Each status change requires:
     - Timestamp
     - Changed by
     - Notes/Comments
     - Optional: Assigned to

2. **Status Flow Details**
   - Ticket creation via channel
   - Ticket validation by Level 1 (review of grievance, review of attachements) -> set status to assigned
   - As the ticket is automatically forwarded to the stakeholders -> set status to in progress
   - In case of resolution, the officer in charge changes the status to resolve and update the resolution details ->set status to resolve
   - If not we follow the escalation channel and then the person who can mark the status to resolve is the Person in Charge of the relevant level.

3. **Priority Levels**:
   - Normal
   - High
   - Gender

### 1.3 Assignment and Routing
- **Assignment Rules**:
  - Based on Project Type
  - Based on Location
  - Based on Priority

- **Auto-Assignment**:
  - First Level: Site Safeguards Focal Person
  - Second Level: PD/PIU Safeguards Focal Person
  - Third Level: Project Office Safeguards Focal Person (GRC Secretariat)
  - Fourth Level: Legal Institutions

## 2. User Roles and Permissions

### 2.1 Role Hierarchy
1. **Super Admin**
   - Full system access
   - User management
   - System configuration

2. **Project Admin**
   - User Management for his project

3. **ADB**
   - View all tickets
   - Generate reports

4. **Project Director (PD)**
   - View all tickets
   - Assign tickets
   - Generate reports

5. **Project Manager (PM)**
   - View assigned project tickets
   - Assign tickets
   - Update status
   - Generate project reports

6. **Contractor**
   - View assigned tickets
   - Update status
   - Add comments
   - Upload attachments

7. **Citizen**
   - Create tickets via channels (no direct access to platform)
   - View own tickets via channels (webchat, whatsapp, facebook)
   - Add comments via channels (webchat, whatsapp, facebook)
   - Upload attachments (webchat, whatsapp, facebook)

### 2.2 Permission Matrix
| Action          | Super Admin | PD | PM | Contractor | Citizen |
|-----------------|-------------|----|----|------------|---------|
| Create Ticket   | ✓          | ✓  | ✓  | ✓         | ✓      |
| View All        | ✓          | ✓  | ×  | ×         | ×      |
| View Assigned   | ✓          | ✓  | ✓  | ✓         | ×      |
| View Own        | ✓          | ✓  | ✓  | ✓         | ✓      |
| Assign          | ✓          | ✓  | ✓  | ×         | ×      |
| Update Status   | ✓          | ✓  | ✓  | ✓         | ×      |
| Add Comment     | ✓          | ✓  | ✓  | ✓         | ✓      |
| Generate Reports| ✓          | ✓  | ✓  | ×         | ×      |

## 3. Project Management

### 3.1 Project Types
- Infrastructure construction (report issues linked to the construction of an infra)
- Infrastructure exploitation and maintenance (report issues on an existing road)
- Other (configurable)

### 3.2 Project Settings
- Default Assignee Escalation Rules
- SLA Rules
- Notification Rules
- Required Fields
- Custom Fields

## 4. SLA and Escalation

### 4.1 SLA Rules
- **Response Time**:
  - Standard: 24 hours

- **Resolution Time by Level**:
  - First Level: 1-2 days
  - Second Level: 7 days
  - Third Level: 15 days
  - Fourth Level: No specific timeline (Legal process)

### 4.2 Escalation Rules

1. **First Level Escalation**:
   - Assigned to: Site Safeguards Focal Person
   - Stakeholders: Contractor, Supervision Consultant (CSC), Site Project Office
   - Timeline: 1-2 days
   - Actions:
     - Initial assessment
     - Basic resolution attempt
     - Documentation of actions taken

2. **Second Level Escalation**:
   - Assigned to: PD/PIU Safeguards Focal Person
   - Stakeholders: Project Directorate (PD), Project Implementation Unit (PIU)
   - Timeline: 7 days
   - Actions:
     - Review of first level actions
     - Coordination with relevant departments
     - Detailed investigation
     - Resolution proposal

3. **Third Level Escalation**:
   - Assigned to: Project Office Safeguards Focal Person (GRC Secretariat)
   - Stakeholders: Grievance Redress Committee (GRC), PIU, Site Office, Affected Persons
   - Timeline: 15 days
   - Actions:
     - GRC review
     - Formal resolution process
     - Stakeholder consultation
     - Final resolution attempt

4. **Fourth Level Escalation**:
   - Assigned to: Legal Institutions
   - Stakeholders: All previous stakeholders
   - Timeline: No specific timeline
   - Actions:
     - Legal review
     - Court proceedings if necessary
     - Legal resolution

### 4.3 Escalation Process
1. **Automatic Triggers**:
   - Timeline exceeded
   - No response within 24 hours
   - Resolution not achieved

2. **Manual Triggers**:
   - Stakeholder request

## 5. Notifications

### 5.1 Trigger Points
- Ticket Creation
- Status Change
- Escalation Level Change
- Timeline Approaching
- Timeline Exceeded

### 5.2 Notification Channels
- SMS
- Email
- Whatsapp

### 5.3 Notification Details
- **Status = New**
  - Level 1 - for action
  - Level 2 - for info
  - Message: "Grievance received - to be reviewed by OIC in 24 hours"

- **Status = Assigned**
  - Level 1 - for action
  - Level 2 - for info
  - User - for info
  - Message: "Grievance verified by OIC - Actions need to be taken to resolve in SLA + grievance_info"

- **Escalation Level Change**
  - Level 1 - for Info
  - Level 2 - for action
  - Level 3 - for Info
  - Level 4 - for Info
  - User - for Info
  - Message: "Grievance Id not resolved in SLA - Escalation Triggered for immediate resolution + grievance_info"

- **Status = Resolved**
  - Level 1 - for Info
  - Level 2 - for Info
  - In case of escalation:
    - Level 3 - for Info
    - Level 4 - for Info
  - Message: "Grievance Id resolved in xx days - Resolution: resolution_details"
  - Message to User: "Your grievance has been resolved - Are you satisfied with the resolution" -> link to resolution flow in chatbot

## 6. Reporting and Analytics

### 6.1 Standard Reports - in app (optional)
- Ticket Volume by Status
- Ticket Volume by timely resolution
- Ticket Volume by escalation level (number of tickets escalated)
- Resolution Time
- Response Time
- Assignment Distribution
- Project-wise Distribution
- User Performance

### 6.2 Monthly Reports (generated and sent by email)
- List of non-resolved escalated tickets
- Monthly performance review per project (number of tickets received, number of tickets resolved, number of tickets escalated by level)
- Each report should have these columns: Project, Priority Level

### 6.3 Custom Reports
- Configurable date ranges
- Custom metrics
- Export options (CSV, PDF, Excel)

## 7. Integration Requirements

### 7.1 Chatbot Integration
- Ticket creation via Rasa
- Status updates
- File attachments
- User verification

### 7.2 Whatsapp Integration
- Ticket creation (via Rasa/Twilio or Whatsapp Business)
- User notification (Grievance Creation, Grievance Status Update)

### 7.3 External Systems
- SMS Gateway
- Email Service
- File Storage
- Authentication Service

## 8. User Interface Requirements

### 8.1 Dashboard
- Ticket Overview
- Recent Activity
- SLA Status
- Team Performance
- Quick Actions

### 8.2 Ticket List
- Filtering
- Sorting
- Bulk Actions
- Quick Status Update
- Search

### 8.3 Ticket Detail
- All ticket information
- Status history
- Comments
- Attachments

## 9. Mobile Responsiveness - optional (mobile interaction will be via whatsapp)
- Responsive design
- Mobile-friendly forms

## 10. Security Requirements

### 10.1 Authentication
- Django authentication system
  - Session-based authentication
  - User model with password hashing
  - CSRF protection
- Password policies
  - Django password validators
  - Password strength requirements
  - Password expiration
- Session security
  - Session timeout
  - Session invalidation on logout
  - Secure session storage
- OAuth/Social authentication (optional)
- 2FA via django-otp (op)

### 10.2 Data Protection
- Encrypted data transmission (HTTPS/TLS)
- Database encryption
  - Field-level encryption via django-fernet-fields
  - Encrypted model fields for sensitive data
  - Secure key management
- Secure file storage
  - Encrypted file storage via django-storages
  - File encryption at rest
- Audit logging
  - django-audit-log for model changes
  - Activity logging for security events
- Data backup
  - Encrypted backups

## 11. Performance Requirements

### 11.1 Response Times
- Page Load: < 2 seconds
- API Response: < 500ms
- Search Results: < 1 second

### 11.2 Scalability
- Support 100+ concurrent users
- Handle 100+ tickets per minute
- Process 1000+ files per day

### 11.3 Database Requirements
- PostgreSQL database
- Automated backups using django-backup
- Indexes on frequently queried fields via Django model Meta class
  - User ID
  - Ticket status
  - Created date
  - Project type
- Query optimization
  - Django model indexes and constraints
  - Django ORM query optimization
- Monitoring via Django Debug Toolbar
  - Query performance
  - Database statistics


