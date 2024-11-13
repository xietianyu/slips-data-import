CREATE TABLE job_execution_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(40) not null,
    status ENUM('success', 'failure','running') NOT NULL DEFAULT 'running',
    plan_no VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);