# Deployment Script for Corrected System V3

Write-Host ("=" * 80)
Write-Host "DEPLOYING CORRECTED SYSTEM V3"
Write-Host ("=" * 80)

# File list
$files = @(
    # Exceptions and validators
    "exceptions.py",
    "validators.py",
    
    # Brain Capacity (CORRECTED)
    "timestamp_manager_corrected.py",
    "state_manager.py",
    "memory_handler.py",
    "brain_core.py",
    
    # Knowledge
    "knowledge_manager.py",
    
    # Intelligence (CORRECTED)
    "intelligence_awareness.py",
    "intelligence_repeat.py",
    "intelligence_explore.py",
    "intelligence_monitor.py",
    "intelligence_future_constraints.py",
    
    # System
    "system_coordinator_corrected.py",
    "system_config_corrected.json",
    
    # Tools
    "documentation_extractor.py",
    "system_flowchart_generator.py",
    "tmrl_live_controller.py",
    
    # Tests
    "test_corrected_system.py"
)

Write-Host ""
Write-Host "Copying files to container..."

$failed = @()
$copied = 0

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  [OK] Copying $file..." -ForegroundColor Green
        docker cp $file mpc_processor:/app/
        
        if ($LASTEXITCODE -eq 0) {
            $copied++
        } else {
            Write-Host "  [FAIL] Failed to copy $file" -ForegroundColor Red
            $failed += $file
        }
    } else {
        Write-Host "  [SKIP] File not found: $file" -ForegroundColor Yellow
    }
}

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed to copy files:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "    $_" }
    exit 1
}

Write-Host ""
Write-Host "All files deployed successfully! ($copied/$($files.Count))" -ForegroundColor Green

# Generate documentation
Write-Host ""
Write-Host "Generating documentation..."
docker exec mpc_processor python3 /app/documentation_extractor.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Documentation generated" -ForegroundColor Green
} else {
    Write-Host "Documentation generation failed" -ForegroundColor Red
}

# Generate flowchart
Write-Host ""
Write-Host "Generating flowchart..."
docker exec mpc_processor python3 /app/system_flowchart_generator.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Flowchart generated" -ForegroundColor Green
} else {
    Write-Host "Flowchart generation failed" -ForegroundColor Red
}

# Run tests
Write-Host ""
Write-Host "Running corrected system tests..."
docker exec mpc_processor python3 /app/test_corrected_system.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "TESTS PASSED!" -ForegroundColor Green
    Write-Host "CORRECTED SYSTEM V3 IS READY" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Tests failed - check logs" -ForegroundColor Red
}

Write-Host ""
Write-Host "Deployment complete!"
Write-Host ("=" * 80)