CREATE TABLE job_execution_results (
    job_id VARCHAR(40) PRIMARY KEY,
    status ENUM('success', 'failure','running') NOT NULL DEFAULT 'running',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);