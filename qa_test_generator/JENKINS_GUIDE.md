# Jenkins Integration Guide

## Overview

The QA Test Generator integrates with Jenkins for CI/CD automation, enabling:

- Automated test execution on code commits
- Scheduled nightly test runs
- Parallel test execution across environments
- Test result aggregation and reporting
- Slack/Email notifications

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Jenkins Setup](#2-jenkins-setup)
3. [Odoo Configuration](#3-odoo-configuration)
4. [Pipeline Configuration](#4-pipeline-configuration)
5. [Webhook Setup](#5-webhook-setup)
6. [Test Execution Flow](#6-test-execution-flow)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

### Jenkins Server Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| Jenkins | 2.400+ | CI/CD server |
| Python | 3.10+ | Robot Framework execution |
| Robot Framework | 6.0+ | Test execution |
| Selenium | 4.0+ | Browser automation |
| Chrome/Firefox | Latest | Browser for testing |
| ChromeDriver/GeckoDriver | Matching browser | WebDriver |

### Required Jenkins Plugins

```
- Pipeline
- Git
- Robot Framework Plugin
- Credentials Binding
- Parameterized Trigger
- Email Extension (optional)
- Slack Notification (optional)
```

### Install on Jenkins Server

```bash
# Install Robot Framework and dependencies
pip install robotframework robotframework-seleniumlibrary robotframework-requests

# Install browser drivers
apt-get install chromium-chromedriver
# or
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE -O /tmp/chromedriver_version
wget https://chromedriver.storage.googleapis.com/$(cat /tmp/chromedriver_version)/chromedriver_linux64.zip
unzip chromedriver_linux64.zip -d /usr/local/bin/
```

---

## 2. Jenkins Setup

### 2.1 Create API Token

1. Log in to Jenkins
2. Click your username → **Configure**
3. **API Token** → **Add new Token**
4. Name: `odoo-qa-integration`
5. Click **Generate** → Copy the token

### 2.2 Create Jenkins Job

#### Option A: Freestyle Project

1. **New Item** → Enter name: `odoo-qa-tests`
2. Select **Freestyle project** → OK
3. Configure:

**General:**
```
☑ This project is parameterized

Add Parameter: String Parameter
  Name: CUSTOMER_CODE
  Default: ALL
  Description: Customer code or ALL for all customers

Add Parameter: String Parameter
  Name: SUITE_ID
  Description: Test Suite ID from Odoo

Add Parameter: String Parameter  
  Name: SERVER_URL
  Description: Target Odoo server URL

Add Parameter: String Parameter
  Name: CALLBACK_URL
  Description: Odoo callback URL for results
```

**Build Environment:**
```
☑ Use secret text(s) or file(s)
  Add → Secret text
    Variable: ODOO_API_KEY
    Credentials: (create Odoo API credential)
```

**Build Steps:**
Add **Execute shell**:
```bash
#!/bin/bash
set -e

# Create output directory
OUTPUT_DIR="output/${BUILD_NUMBER}"
mkdir -p "$OUTPUT_DIR"

# Download test files from Odoo
curl -H "Authorization: Bearer ${ODOO_API_KEY}" \
     "${CALLBACK_URL}/api/v1/qa/download/${SUITE_ID}" \
     -o tests.zip

unzip tests.zip -d tests/

# Run Robot Framework tests
robot \
    --variable SERVER_URL:${SERVER_URL} \
    --variable HEADLESS:true \
    --outputdir "$OUTPUT_DIR" \
    --loglevel DEBUG \
    tests/

# Upload results back to Odoo
curl -X POST \
     -H "Authorization: Bearer ${ODOO_API_KEY}" \
     -F "output_xml=@${OUTPUT_DIR}/output.xml" \
     -F "log_html=@${OUTPUT_DIR}/log.html" \
     -F "report_html=@${OUTPUT_DIR}/report.html" \
     "${CALLBACK_URL}/api/v1/qa/results/${SUITE_ID}"
```

**Post-build Actions:**
```
☑ Publish Robot Framework test results
  Directory: output/${BUILD_NUMBER}
  
☑ Email Notification (optional)
  Recipients: qa-team@company.com
```

#### Option B: Pipeline (Recommended)

1. **New Item** → Enter name: `odoo-qa-pipeline`
2. Select **Pipeline** → OK
3. **Pipeline** section → **Pipeline script from SCM** or paste directly:

```groovy
pipeline {
    agent any
    
    parameters {
        string(name: 'CUSTOMER_CODE', defaultValue: 'ALL', description: 'Customer code')
        string(name: 'SUITE_ID', description: 'Test Suite ID')
        string(name: 'SERVER_URL', description: 'Target Odoo URL')
        string(name: 'CALLBACK_URL', description: 'Odoo callback URL')
        string(name: 'RUN_ID', description: 'Test Run ID in Odoo')
    }
    
    environment {
        ODOO_API_KEY = credentials('odoo-api-key')
    }
    
    stages {
        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install robotframework robotframework-seleniumlibrary
                '''
            }
        }
        
        stage('Download Tests') {
            steps {
                sh '''
                    curl -H "Authorization: Bearer ${ODOO_API_KEY}" \
                         "${CALLBACK_URL}/api/v1/qa/download/${SUITE_ID}" \
                         -o tests.zip
                    unzip -o tests.zip -d tests/
                '''
            }
        }
        
        stage('Run Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    robot \
                        --variable SERVER_URL:${SERVER_URL} \
                        --variable HEADLESS:true \
                        --outputdir output \
                        --loglevel DEBUG \
                        tests/ || true
                '''
            }
        }
        
        stage('Upload Results') {
            steps {
                sh '''
                    curl -X POST \
                         -H "Authorization: Bearer ${ODOO_API_KEY}" \
                         -F "run_id=${RUN_ID}" \
                         -F "output_xml=@output/output.xml" \
                         -F "log_html=@output/log.html" \
                         -F "report_html=@output/report.html" \
                         -F "screenshots=@output/selenium-*.png" \
                         "${CALLBACK_URL}/api/v1/qa/results"
                '''
            }
        }
    }
    
    post {
        always {
            robot outputPath: 'output', passThreshold: 80.0
            archiveArtifacts artifacts: 'output/**/*', allowEmptyArchive: true
        }
        failure {
            emailext (
                subject: "QA Tests Failed: ${CUSTOMER_CODE}",
                body: "Test suite ${SUITE_ID} failed. Check Jenkins for details.",
                recipientProviders: [[$class: 'DevelopersRecipientProvider']]
            )
        }
    }
}
```

### 2.3 Multi-Customer Pipeline

For running tests across multiple customers:

```groovy
pipeline {
    agent any
    
    parameters {
        choice(name: 'CUSTOMERS', choices: ['ALL', 'ACME', 'TECHCORP', 'BIGRETAIL'], description: 'Select customer(s)')
    }
    
    stages {
        stage('Get Customer List') {
            steps {
                script {
                    def response = httpRequest(
                        url: "${ODOO_URL}/api/v1/qa/customers",
                        customHeaders: [[name: 'Authorization', value: "Bearer ${ODOO_API_KEY}"]]
                    )
                    env.CUSTOMERS_JSON = response.content
                }
            }
        }
        
        stage('Run Tests') {
            steps {
                script {
                    def customers = readJSON text: env.CUSTOMERS_JSON
                    def parallelStages = [:]
                    
                    customers.each { customer ->
                        if (params.CUSTOMERS == 'ALL' || params.CUSTOMERS == customer.code) {
                            parallelStages[customer.code] = {
                                stage("Test ${customer.code}") {
                                    build job: 'odoo-qa-pipeline',
                                        parameters: [
                                            string(name: 'CUSTOMER_CODE', value: customer.code),
                                            string(name: 'SUITE_ID', value: customer.default_suite_id),
                                            string(name: 'SERVER_URL', value: customer.staging_url)
                                        ],
                                        wait: true
                                }
                            }
                        }
                    }
                    
                    parallel parallelStages
                }
            }
        }
    }
}
```

---

## 3. Odoo Configuration

### 3.1 Configure AI Settings

Navigate to: **QA Testing → Configuration → AI Settings**

| Field | Value |
|-------|-------|
| Jenkins Enabled | ☑ Checked |
| Jenkins URL | `https://jenkins.yourcompany.com` |
| Jenkins User | `odoo-integration` |
| Jenkins Token | `(paste API token)` |
| Job Name | `odoo-qa-pipeline` |

Click **Test Jenkins Connection** to verify.

### 3.2 Configure Customer Servers

For each customer, set up the server that Jenkins will test against:

Navigate to: **QA Testing → Customers → [Customer] → Servers**

| Field | Value |
|-------|-------|
| Server Name | `ACME Staging` |
| Environment | `Staging` |
| URL | `https://acme-staging.odoo.com` |
| Database | `acme_staging` |

### 3.3 API Endpoint Reference

The module exposes these REST endpoints for Jenkins:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/qa/download/<suite_id>` | GET | Download test files as ZIP |
| `/api/v1/qa/results` | POST | Upload test results |
| `/api/v1/qa/customers` | GET | List customers and suites |
| `/api/v1/qa/trigger/<suite_id>` | POST | Trigger test run |
| `/api/v1/qa/status/<run_id>` | GET | Get run status |

---

## 4. Pipeline Configuration

### 4.1 Environment Variables

Create these in Jenkins **Manage Jenkins → Configure System → Global properties**:

| Variable | Description | Example |
|----------|-------------|---------|
| `ODOO_URL` | Odoo base URL | `https://qa-hub.yourcompany.com` |
| `ROBOT_BROWSER` | Default browser | `chrome` |
| `ROBOT_HEADLESS` | Run headless | `true` |
| `SCREENSHOT_ON_FAIL` | Capture on failure | `true` |

### 4.2 Credentials Setup

**Manage Jenkins → Credentials → System → Global credentials**

Add credentials:

1. **Odoo API Key**
   - Kind: Secret text
   - ID: `odoo-api-key`
   - Secret: (your Odoo API key)

2. **SSH Key for Servers** (if needed)
   - Kind: SSH Username with private key
   - ID: `odoo-server-ssh`
   - Username: `odoo`
   - Private Key: (paste key)

### 4.3 Node Configuration

For distributed testing, configure Jenkins agents:

```groovy
pipeline {
    agent {
        label 'robot-framework'  // Agent with Robot Framework installed
    }
    // ...
}
```

Agent requirements:
- Python 3.10+
- Robot Framework
- Chrome/Firefox + WebDriver
- Network access to customer Odoo servers

---

## 5. Webhook Setup

### 5.1 Trigger from Git Push

Configure webhook in your Git repository:

**GitHub:**
1. Repository → Settings → Webhooks → Add webhook
2. Payload URL: `https://jenkins.yourcompany.com/github-webhook/`
3. Content type: `application/json`
4. Events: `Push`, `Pull request`

**GitLab:**
1. Project → Settings → Webhooks
2. URL: `https://jenkins.yourcompany.com/project/odoo-qa-pipeline`
3. Trigger: `Push events`, `Merge request events`

### 5.2 Trigger from Odoo

The module can trigger Jenkins builds programmatically:

```python
# In qa_test_generator/services/jenkins_client.py
def trigger_build(self, suite_id, server_id, run_id):
    """Trigger Jenkins build for test suite"""
    params = {
        'SUITE_ID': suite_id,
        'SERVER_URL': self._get_server_url(server_id),
        'RUN_ID': run_id,
        'CALLBACK_URL': self.odoo_url,
    }
    
    response = requests.post(
        f"{self.jenkins_url}/job/{self.job_name}/buildWithParameters",
        auth=(self.username, self.token),
        params=params
    )
    return response.status_code == 201
```

### 5.3 Scheduled Triggers

Configure scheduled runs in Jenkins:

**Build Triggers:**
```
☑ Build periodically
  Schedule: H 2 * * *  # Run at 2 AM daily
```

Or use parameterized scheduler:
```
☑ Parameterized Scheduler
  H 2 * * * % CUSTOMER_CODE=ACME
  H 3 * * * % CUSTOMER_CODE=TECHCORP
  H 4 * * * % CUSTOMER_CODE=BIGRETAIL
```

---

## 6. Test Execution Flow

### 6.1 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TEST EXECUTION FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐               │
│  │  Odoo   │     │ Jenkins │     │ Target  │     │  Odoo   │               │
│  │   QA    │────▶│  Build  │────▶│ Server  │────▶│ Results │               │
│  │   Hub   │     │         │     │         │     │         │               │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘               │
│       │               │               │               │                     │
│       │  1. Trigger   │               │               │                     │
│       │──────────────▶│               │               │                     │
│       │               │               │               │                     │
│       │  2. Download  │               │               │                     │
│       │◀──────────────│               │               │                     │
│       │    Tests      │               │               │                     │
│       │               │               │               │                     │
│       │               │  3. Execute   │               │                     │
│       │               │──────────────▶│               │                     │
│       │               │    Tests      │               │                     │
│       │               │               │               │                     │
│       │               │  4. Results   │               │                     │
│       │               │◀──────────────│               │                     │
│       │               │               │               │                     │
│       │               │  5. Upload    │               │                     │
│       │◀──────────────│──────────────────────────────▶│                     │
│       │    Results    │               │               │                     │
│       │               │               │               │                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Step-by-Step Process

1. **Trigger** (Odoo → Jenkins)
   - User clicks "Run Suite" in Odoo
   - Or scheduled cron triggers
   - Odoo calls Jenkins API with parameters

2. **Download** (Jenkins → Odoo)
   - Jenkins fetches test files from Odoo API
   - Robot Framework `.robot` files
   - Resource files and keywords
   - Test data/fixtures

3. **Execute** (Jenkins → Target Server)
   - Jenkins runs Robot Framework
   - Tests interact with customer's Odoo
   - Screenshots captured on failure
   - Logs generated

4. **Collect** (Jenkins)
   - Robot Framework generates:
     - `output.xml` - Machine-readable results
     - `log.html` - Detailed execution log
     - `report.html` - Summary report
     - Screenshots

5. **Upload** (Jenkins → Odoo)
   - Jenkins POSTs results to Odoo API
   - Odoo parses `output.xml`
   - Updates test run status
   - Stores artifacts

### 6.3 Result Processing

Odoo processes Jenkins results:

```python
# Simplified result processing
def process_jenkins_results(self, run_id, output_xml):
    from robot.api import ExecutionResult
    
    result = ExecutionResult(output_xml)
    
    run = self.env['qa.test.run'].browse(run_id)
    
    # Update run statistics
    run.write({
        'total_tests': result.statistics.total.total,
        'passed_tests': result.statistics.total.passed,
        'failed_tests': result.statistics.total.failed,
        'pass_rate': result.statistics.total.passed / result.statistics.total.total * 100,
        'state': 'passed' if result.statistics.total.failed == 0 else 'failed',
        'end_time': fields.Datetime.now(),
    })
    
    # Create individual test results
    for test in result.suite.all_tests:
        self.env['qa.test.result'].create({
            'run_id': run_id,
            'test_case_id': self._find_test_case(test.name),
            'status': 'passed' if test.passed else 'failed',
            'duration': test.elapsedtime / 1000,
            'error_message': test.message if not test.passed else False,
        })
```

---

## 7. Troubleshooting

### 7.1 Common Issues

#### Jenkins Cannot Connect to Odoo

**Symptom:** Build fails at "Download Tests" stage

**Solutions:**
```bash
# Check network connectivity
curl -v https://qa-hub.yourcompany.com/api/v1/qa/health

# Check API key
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://qa-hub.yourcompany.com/api/v1/qa/customers

# Check firewall rules
# Jenkins server needs outbound access to Odoo
```

#### Robot Framework Tests Fail to Start

**Symptom:** "No browser available" or "WebDriver not found"

**Solutions:**
```bash
# Install ChromeDriver
apt-get update && apt-get install -y chromium-chromedriver

# Or for specific version
CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+')
wget https://chromedriver.storage.googleapis.com/${CHROME_VERSION}/chromedriver_linux64.zip

# Set PATH
export PATH=$PATH:/usr/local/bin

# Test Robot Framework
robot --version
```

#### Tests Run But Results Not Uploaded

**Symptom:** Jenkins build succeeds but Odoo shows "Running"

**Solutions:**
```bash
# Check callback URL
echo $CALLBACK_URL  # Should be https://qa-hub.yourcompany.com

# Test upload manually
curl -X POST \
     -H "Authorization: Bearer ${ODOO_API_KEY}" \
     -F "run_id=123" \
     -F "output_xml=@output/output.xml" \
     "${CALLBACK_URL}/api/v1/qa/results"

# Check Odoo logs
tail -f /var/log/odoo/odoo.log | grep "qa.test"
```

#### Timeout During Test Execution

**Symptom:** Tests hang or timeout

**Solutions:**
```groovy
// In Jenkinsfile - add timeout
stage('Run Tests') {
    timeout(time: 30, unit: 'MINUTES') {
        steps {
            sh 'robot ...'
        }
    }
}
```

```bash
# In robot command - add timeout
robot --timeout 5min tests/
```

### 7.2 Debug Mode

Enable debug logging:

**Jenkins:**
```groovy
environment {
    ROBOT_LOGLEVEL = 'DEBUG'
    ROBOT_DEBUG = 'true'
}
```

**Robot Framework:**
```bash
robot \
    --loglevel DEBUG:INFO \
    --debugfile debug.txt \
    tests/
```

**Odoo:**
```ini
# In odoo.conf
log_level = debug
log_handler = qa_test_generator:DEBUG
```

### 7.3 Health Check Script

Create a health check job in Jenkins:

```bash
#!/bin/bash
# health_check.sh

echo "=== QA System Health Check ==="

# Check Odoo API
echo -n "Odoo API: "
curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${ODOO_API_KEY}" \
    "${ODOO_URL}/api/v1/qa/health" && echo " OK" || echo " FAIL"

# Check Robot Framework
echo -n "Robot Framework: "
robot --version > /dev/null 2>&1 && echo "OK" || echo "FAIL"

# Check Chrome
echo -n "Chrome: "
google-chrome --version > /dev/null 2>&1 && echo "OK" || echo "FAIL"

# Check ChromeDriver
echo -n "ChromeDriver: "
chromedriver --version > /dev/null 2>&1 && echo "OK" || echo "FAIL"

# Check connectivity to customer servers
echo "=== Customer Servers ==="
for url in "https://acme-staging.odoo.com" "https://techcorp-staging.odoo.com"; do
    echo -n "$url: "
    curl -s -o /dev/null -w "%{http_code}" "$url/web/login" && echo " OK" || echo " FAIL"
done
```

---

## Quick Reference

### Jenkins API Endpoints

| Action | Endpoint |
|--------|----------|
| Trigger build | `POST /job/{name}/buildWithParameters` |
| Get build status | `GET /job/{name}/{build}/api/json` |
| Get console output | `GET /job/{name}/{build}/consoleText` |
| Stop build | `POST /job/{name}/{build}/stop` |

### Robot Framework CLI Options

| Option | Description |
|--------|-------------|
| `--variable NAME:VALUE` | Set variable |
| `--outputdir DIR` | Output directory |
| `--loglevel LEVEL` | Log level (DEBUG, INFO, WARN) |
| `--include TAG` | Include tests by tag |
| `--exclude TAG` | Exclude tests by tag |
| `--timeout TIME` | Test timeout |
| `--exitonfailure` | Stop on first failure |

### Odoo QA API Reference

| Endpoint | Method | Parameters |
|----------|--------|------------|
| `/api/v1/qa/download/{suite_id}` | GET | - |
| `/api/v1/qa/results` | POST | run_id, output_xml, log_html, report_html |
| `/api/v1/qa/trigger/{suite_id}` | POST | server_id |
| `/api/v1/qa/status/{run_id}` | GET | - |
| `/api/v1/qa/customers` | GET | active=true |

---

## Support

For issues with Jenkins integration:
1. Check Jenkins build logs
2. Check Odoo server logs
3. Verify network connectivity
4. Test API endpoints manually

**Version:** 18.0.1.0.0
**Last Updated:** January 2026
