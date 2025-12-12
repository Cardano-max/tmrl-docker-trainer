# Production Deployment Script V3

Write-Host ("=" * 80)
Write-Host "DEPLOYING PRODUCTION SYSTEM V3"
Write-Host ("=" * 80)

# List of files to deploy
$files = @(
    "exceptions.py",
    "validators.py",
    "state_manager.py",
    "memory_handler.py",
    "timestamp_manager.py",
    "intelligence_monitor.py",
    "intelligence_sensorial.py",
    "intelligence_future_constraints.py",
    "intelligence_repeat_v3.py",
    "brain_capacity_v2.py",
    "knowledge_manager.py",
    "intelligence_explore.py",
    "system_coordinator_v3.py",
    "system_config_v3.json",
    "test_complete_system_v3.py"
)

Write-Host "`nCopying files to container..."

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  [OK] Copying $file..." -ForegroundColor Green
        docker cp $file mpc_processor:/app/

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [ERROR] Failed to copy $file" -ForegroundColor Red
            exit 1
        }
    }
    else {
        Write-Host "  [ERROR] File not found: $file" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`nAll files deployed successfully!" -ForegroundColor Green

# Run tests
Write-Host "`nRunning System V3 tests..." -ForegroundColor Yellow
docker exec mpc_processor python3 /app/test_complete_system_v3.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nTESTS PASSED - SYSTEM V3 READY!" -ForegroundColor Green
}
else {
    Write-Host "`nTESTS FAILED - CHECK LOGS" -ForegroundColor Red
}

Write-Host "`nDeployment complete!"
Write-Host ("=" * 80)
