-- Voice Processing Schema

-- Grievance Files Table
CREATE TABLE IF NOT EXISTS grievance_files (
    file_id UUID PRIMARY KEY,
    grievance_id UUID NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size BIGINT NOT NULL,
    language_code VARCHAR(10) DEFAULT 'ne',
    upload_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id) ON DELETE CASCADE
);

-- Task Records Table
CREATE TABLE IF NOT EXISTS task_records (
    task_id UUID PRIMARY KEY,
    grievance_id UUID NOT NULL,
    task_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    execution_time_ms INTEGER,
    result_text TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id) ON DELETE CASCADE
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_grievance_files_grievance_id ON grievance_files(grievance_id);
CREATE INDEX IF NOT EXISTS idx_grievance_files_file_type ON grievance_files(file_type);
CREATE INDEX IF NOT EXISTS idx_task_records_grievance_id ON task_records(grievance_id);
CREATE INDEX IF NOT EXISTS idx_task_records_status ON task_records(status);

-- Add triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_grievance_files_updated_at
    BEFORE UPDATE ON grievance_files
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_records_updated_at
    BEFORE UPDATE ON task_records
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add voice processing specific columns to grievances table
ALTER TABLE grievances
ADD COLUMN IF NOT EXISTS language_code VARCHAR(10) DEFAULT 'ne',
ADD COLUMN IF NOT EXISTS grievance_details TEXT,
ADD COLUMN IF NOT EXISTS user_full_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS user_contact_phone VARCHAR(50),
ADD COLUMN IF NOT EXISTS user_address TEXT,
ADD COLUMN IF NOT EXISTS classification_summary TEXT,
ADD COLUMN IF NOT EXISTS classification_categories TEXT[];

-- Add indexes for new columns
CREATE INDEX IF NOT EXISTS idx_grievances_language_code ON grievances(language_code);
CREATE INDEX IF NOT EXISTS idx_grievances_user_contact_phone ON grievances(user_contact_phone); 