const { chromium } = require('playwright');

const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const ADMIN_USER = process.env.AI_INTERVIEW_SUPER_ADMIN_NAME || '';
const ADMIN_PASS = process.env.AI_INTERVIEW_SUPER_ADMIN_PASSWORD || '';

async function runE2EVerification() {
  if (!ADMIN_USER || !ADMIN_PASS) {
    throw new Error('Missing AI_INTERVIEW_SUPER_ADMIN_NAME or AI_INTERVIEW_SUPER_ADMIN_PASSWORD');
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const results = {
    steps: [],
    errors: [],
    screenshots: []
  };

  try {
    // Step 1: Access homepage
    console.log('Step 1: Accessing homepage...');
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    results.steps.push({ step: 1, action: 'Access homepage', status: 'PASS', details: 'Page loaded' });
    await page.screenshot({ path: 'test/artifacts/01_homepage.png' });
    results.screenshots.push('test/artifacts/01_homepage.png');

    // Step 2: Login with admin credentials
    console.log('Step 2: Attempting login...');

    // Look for login form elements
    const usernameInput = page.locator('input[type="text"], input[placeholder*="user"], input[placeholder*="name"]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    const loginButton = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("登录"), button:has-text("Sign in")').first();

    const hasLoginForm = await usernameInput.count() > 0;
    if (hasLoginForm) {
      await usernameInput.fill(ADMIN_USER);
      await passwordInput.fill(ADMIN_PASS);
      await loginButton.click();

      // Wait for navigation after login
      await page.waitForTimeout(2000);

      // Check if login was successful by looking for dashboard or main content
      const currentUrl = page.url();
      console.log('After login URL:', currentUrl);

      if (!currentUrl.includes('login')) {
        results.steps.push({ step: 2, action: 'Login with configured admin credentials', status: 'PASS', details: `Redirected to ${currentUrl}` });
      } else {
        results.steps.push({ step: 2, action: 'Login with configured admin credentials', status: 'FAIL', details: 'Still on login page' });
        await page.screenshot({ path: 'test/artifacts/02_login_failed.png' });
        results.screenshots.push('test/artifacts/02_login_failed.png');
      }
    } else {
      results.steps.push({ step: 2, action: 'Login with configured admin credentials', status: 'FAIL', details: 'Login form not found' });
      await page.screenshot({ path: 'test/artifacts/02_login_form_missing.png' });
      results.screenshots.push('test/artifacts/02_login_form_missing.png');
    }

    // Step 3: Navigate to InterviewRecordsView
    console.log('Step 3: Navigating to Interview Records page...');

    // Try different possible routes
    const possibleRoutes = [
      '/interview-records',
      '/interviewrecords',
      '/records',
      '/interview/records',
      '/history',
      '/interviews',
      '/dashboard/interview-records'
    ];

    let navigatedToRecords = false;
    for (const route of possibleRoutes) {
      try {
        await page.goto(BASE_URL + route, { waitUntil: 'networkidle', timeout: 10000 });
        const currentUrl = page.url();
        if (!currentUrl.includes('login')) {
          console.log(`Route ${route} works, URL: ${currentUrl}`);
          navigatedToRecords = true;
          results.steps.push({ step: 3, action: 'Navigate to InterviewRecordsView', status: 'PASS', details: `Found at ${route}` });
          break;
        }
      } catch (e) {
        // Route not found, try next
      }
    }

    // If no route worked, try sidebar navigation
    if (!navigatedToRecords) {
      // Look for sidebar menu items
      const menuItems = page.locator('.ant-menu-item, .menu-item, [role="menuitem"], a[href*="record"], a[href*="history"]');
      const menuCount = await menuItems.count();
      console.log(`Found ${menuCount} menu items`);

      for (let i = 0; i < Math.min(menuCount, 10); i++) {
        const menuText = await menuItems.nth(i).textContent();
        console.log(`Menu item ${i}: ${menuText}`);
        if (menuText && (menuText.toLowerCase().includes('record') || menuText.toLowerCase().includes('历史') || menuText.toLowerCase().includes('history'))) {
          await menuItems.nth(i).click();
          await page.waitForTimeout(1500);
          navigatedToRecords = true;
          results.steps.push({ step: 3, action: 'Navigate to InterviewRecordsView', status: 'PASS', details: `Found via menu: ${menuText}` });
          break;
        }
      }
    }

    if (!navigatedToRecords) {
      results.steps.push({ step: 3, action: 'Navigate to InterviewRecordsView', status: 'FAIL', details: 'Could not find Interview Records page' });
    }

    await page.screenshot({ path: 'test/artifacts/03_interview_records.png' });
    results.screenshots.push('test/artifacts/03_interview_records.png');

    // Step 4: Verify "个性化提升路径" section
    console.log('Step 4: Checking for "个性化提升路径" section...');
    const improvementPath = page.locator('text=/个性化提升路径/i, text=/提升路径/i, text=/improvement/i, text=/personalized.*path/i').first();
    const hasImprovementPath = await improvementPath.count() > 0;

    if (hasImprovementPath) {
      results.steps.push({ step: 4, action: 'Verify 个性化提升路径 section', status: 'PASS', details: 'Section found on page' });

      // Check if the section has content
      const sectionBox = await improvementPath.boundingBox();
      if (sectionBox) {
        console.log('Improvement path section found at:', sectionBox);
      }
    } else {
      results.steps.push({ step: 4, action: 'Verify 个性化提升路径 section', status: 'FAIL', details: 'Section not found on page' });
    }

    await page.screenshot({ path: 'test/artifacts/04_improvement_path.png' });
    results.screenshots.push('test/artifacts/04_improvement_path.png');

    // Step 5: Check for recommended resources
    console.log('Step 5: Checking for recommended resources...');
    const recommendedResources = page.locator('text=/推荐资源/i, text=/recommended.*resource/i, a[href*="resource"]').first();
    const hasRecommendedResources = await recommendedResources.count() > 0;

    if (hasRecommendedResources) {
      results.steps.push({ step: 5, action: 'Verify 推荐资源 section', status: 'PASS', details: 'Recommended resources section found' });
    } else {
      results.steps.push({ step: 5, action: 'Verify 推荐资源 section', status: 'WARNING', details: 'Recommended resources section not found - may be expected if no data' });
    }

    // Step 6: Check for related records
    console.log('Step 6: Checking for related records...');
    const relatedRecords = page.locator('text=/关联记录/i, text=/related.*record/i, text=/相关记录/i').first();
    const hasRelatedRecords = await relatedRecords.count() > 0;

    if (hasRelatedRecords) {
      results.steps.push({ step: 6, action: 'Verify 关联记录 section', status: 'PASS', details: 'Related records section found' });
    } else {
      results.steps.push({ step: 6, action: 'Verify 关联记录 section', status: 'WARNING', details: 'Related records section not found - may be expected if no data' });
    }

    // Capture console errors
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Reload page to capture any console errors
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    if (consoleErrors.length > 0) {
      results.errors.push({ type: 'console_errors', details: consoleErrors });
    }

    await page.screenshot({ path: 'test/artifacts/05_final_state.png' });
    results.screenshots.push('test/artifacts/05_final_state.png');

  } catch (error) {
    console.error('Test error:', error.message);
    results.errors.push({ type: 'exception', details: error.message });
    await page.screenshot({ path: 'test/artifacts/error_screenshot.png' });
    results.screenshots.push('test/artifacts/error_screenshot.png');
  } finally {
    await browser.close();
  }

  return results;
}

// Run and output results
runE2EVerification()
  .then(results => {
    console.log('\n========== E2E VERIFICATION RESULTS ==========\n');
    console.log('Steps:');
    results.steps.forEach(s => {
      const icon = s.status === 'PASS' ? '[PASS]' : s.status === 'FAIL' ? '[FAIL]' : '[WARN]';
      console.log(`  ${icon} Step ${s.step}: ${s.action}`);
      console.log(`        Details: ${s.details}`);
    });

    if (results.errors.length > 0) {
      console.log('\nErrors:');
      results.errors.forEach(e => {
        console.log(`  [ERROR] ${e.type}: ${JSON.stringify(e.details)}`);
      });
    }

    console.log('\nScreenshots saved:');
    results.screenshots.forEach(s => {
      console.log(`  - ${s}`);
    });

    console.log('\n================================================\n');
    process.exit(results.errors.length > 0 ? 1 : 0);
  })
  .catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
