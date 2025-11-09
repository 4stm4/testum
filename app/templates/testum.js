/**
 * Testum - Theme and i18n utilities
 */

// ===== THEME MANAGEMENT =====
const THEME_KEY = 'testum-theme';
const LANG_KEY = 'testum-language';

// Get current theme
function getCurrentTheme() {
    return localStorage.getItem(THEME_KEY) || 'dark';
}

// Get current language
function getCurrentLanguage() {
    return localStorage.getItem(LANG_KEY) || 'en';
}

// Apply theme
function applyTheme(theme) {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    
    // Update theme toggle button
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
        themeToggle.title = theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme';
    }
}

// Toggle theme
function toggleTheme() {
    const currentTheme = getCurrentTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
}

// ===== i18n TRANSLATIONS =====
const translations = {
    en: {
        // Header
        logout: 'Logout',
        
        // Sidebar
        resources: 'Resources',
        dashboard: 'Dashboard',
        sshKeys: 'SSH Keys',
        platforms: 'Platforms',
        system: 'System',
        settings: 'Settings',
        healthCheck: 'Health Check',
        apiDocs: 'API Docs',
        
        // Dashboard
        welcomeTitle: '🔐 Testum',
        welcomeSubtitle: 'SSH Platform Management',
        welcomeDescription: 'Manage SSH keys and platforms with ease',
        sshKeysCard: 'SSH Keys',
        sshKeysDescription: 'Manage public SSH keys for deployment',
        platformsCard: 'Platforms',
        platformsDescription: 'Configure target SSH hosts',
        tasksCard: 'Tasks',
        tasksDescription: 'Monitor running tasks',
        statsTitle: 'Statistics',
        totalKeys: 'Total Keys',
        totalPlatforms: 'Total Platforms',
        activeTasks: 'Active Tasks',
        
        // SSH Keys Page
        sshKeysTitle: 'SSH Keys',
        sshKeysSubtitle: 'Manage SSH public keys for deployment to platforms',
        addNewKey: 'Add New Key',
        keyName: 'Key Name',
        publicKey: 'Public Key',
        addKey: 'Add Key',
        existingKeys: 'Existing Keys',
        noKeysFound: 'No SSH keys found. Add your first key above.',
        created: 'Created',
        delete: 'Delete',
        
        // Platforms Page
        platformsTitle: 'Platforms',
        platformsSubtitle: 'Manage target SSH platforms for key deployment and command execution',
        addNewPlatform: 'Add New Platform',
        platformName: 'Platform Name',
        host: 'Host',
        port: 'Port',
        username: 'Username',
        authMethod: 'Authentication Method',
        password: 'Password',
        privateKey: 'Private Key',
        addPlatform: 'Add Platform',
        existingPlatforms: 'Existing Platforms',
        noPlatformsFound: 'No platforms found. Add your first platform above.',
        deployKeys: 'Deploy Keys',
        runCommand: 'Run Command',
        
        // Settings Page
        settingsTitle: 'Settings',
        settingsSubtitle: 'Manage your account settings and preferences',
        accountInfo: 'Account Information',
        accountInfoDesc: 'View your current account details',
        currentUsername: 'Current Username',
        accountType: 'Account Type',
        administrator: 'Administrator',
        
        appSettings: 'Application Settings',
        appSettingsDesc: 'Core application configuration (read-only, update via docker-compose.yml)',
        environment: 'Environment',
        secretKey: 'Secret Key',
        fernetKey: 'Fernet Encryption Key',
        fernetKeyDesc: 'Used for encrypting passwords and private keys',
        hiddenForSecurity: 'Hidden for security. Change in docker-compose.yml if needed.',
        
        databaseSettings: 'Database Settings',
        databaseSettingsDesc: 'Database connection configuration (read-only)',
        databaseUrl: 'Database URL',
        redisUrl: 'Redis URL',
        
        taskQueueSettings: 'Task Queue Settings',
        taskQueueSettingsDesc: 'Celery task queue configuration (read-only)',
        brokerUrl: 'Broker URL',
        resultBackend: 'Result Backend',
        
        storageSettings: 'Storage Settings',
        storageSettingsDesc: 'MinIO S3-compatible storage configuration (read-only)',
        minioEndpoint: 'MinIO Endpoint',
        bucketName: 'Bucket Name',
        accessKey: 'Access Key',
        secureConnection: 'Secure Connection (TLS)',
        
        sshSettings: 'SSH Settings',
        sshSettingsDesc: 'SSH connection behavior configuration',
        hostKeyPolicy: 'Host Key Policy',
        autoAddDesc: 'auto_add = Automatically accept new host keys (TOFU - Trust On First Use)',
        
        changeUsername: 'Change Username',
        changeUsernameDesc: 'Update your login username. You will need to log in again after changing it.',
        currentPasswordForVerification: 'Current Password (for verification)',
        newUsername: 'New Username',
        updateUsername: 'Update Username',
        
        changePassword: 'Change Password',
        changePasswordDesc: 'Update your password to keep your account secure. Use a strong password with at least 8 characters.',
        currentPassword: 'Current Password',
        newPassword: 'New Password',
        confirmPassword: 'Confirm New Password',
        updatePassword: 'Update Password',
        
        noteTitle: 'Note:',
        noteText: 'After changing your username or password, you will be automatically logged out and need to sign in again with your new credentials.',
        
        // Login Page
        welcomeBack: 'Welcome Back',
        loginPrompt: 'Please enter your credentials to continue',
        signIn: 'Sign In',
        signingIn: 'Signing in...',
        
        // Messages
        loading: 'Loading...',
        yes: 'Yes',
        no: 'No',
        
        // Theme & Language
        themeLight: 'Switch to Light Theme',
        themeDark: 'Switch to Dark Theme',
    },
    
    ru: {
        // Header
        logout: 'Выход',
        
        // Sidebar
        resources: 'Ресурсы',
        dashboard: 'Панель управления',
        sshKeys: 'SSH Ключи',
        platforms: 'Платформы',
        system: 'Система',
        settings: 'Настройки',
        healthCheck: 'Проверка здоровья',
        apiDocs: 'API Документация',
        
        // Dashboard
        welcomeTitle: '🔐 Testum',
        welcomeSubtitle: 'Управление SSH платформами',
        welcomeDescription: 'Управляйте SSH ключами и платформами с легкостью',
        sshKeysCard: 'SSH Ключи',
        sshKeysDescription: 'Управление публичными SSH ключами для развертывания',
        platformsCard: 'Платформы',
        platformsDescription: 'Настройка целевых SSH хостов',
        tasksCard: 'Задачи',
        tasksDescription: 'Мониторинг выполняемых задач',
        statsTitle: 'Статистика',
        totalKeys: 'Всего ключей',
        totalPlatforms: 'Всего платформ',
        activeTasks: 'Активных задач',
        
        // SSH Keys Page
        sshKeysTitle: 'SSH Ключи',
        sshKeysSubtitle: 'Управление публичными SSH ключами для развертывания на платформах',
        addNewKey: 'Добавить новый ключ',
        keyName: 'Название ключа',
        publicKey: 'Публичный ключ',
        addKey: 'Добавить ключ',
        existingKeys: 'Существующие ключи',
        noKeysFound: 'SSH ключи не найдены. Добавьте первый ключ выше.',
        created: 'Создан',
        delete: 'Удалить',
        
        // Platforms Page
        platformsTitle: 'Платформы',
        platformsSubtitle: 'Управление целевыми SSH платформами для развертывания ключей и выполнения команд',
        addNewPlatform: 'Добавить новую платформу',
        platformName: 'Название платформы',
        host: 'Хост',
        port: 'Порт',
        username: 'Имя пользователя',
        authMethod: 'Метод аутентификации',
        password: 'Пароль',
        privateKey: 'Приватный ключ',
        addPlatform: 'Добавить платформу',
        existingPlatforms: 'Существующие платформы',
        noPlatformsFound: 'Платформы не найдены. Добавьте первую платформу выше.',
        deployKeys: 'Развернуть ключи',
        runCommand: 'Выполнить команду',
        
        // Settings Page
        settingsTitle: 'Настройки',
        settingsSubtitle: 'Управление настройками учетной записи и предпочтениями',
        accountInfo: 'Информация об учетной записи',
        accountInfoDesc: 'Просмотр текущих данных учетной записи',
        currentUsername: 'Текущее имя пользователя',
        accountType: 'Тип учетной записи',
        administrator: 'Администратор',
        
        appSettings: 'Настройки приложения',
        appSettingsDesc: 'Основная конфигурация приложения (только чтение, изменение через docker-compose.yml)',
        environment: 'Окружение',
        secretKey: 'Секретный ключ',
        fernetKey: 'Ключ шифрования Fernet',
        fernetKeyDesc: 'Используется для шифрования паролей и приватных ключей',
        hiddenForSecurity: 'Скрыто в целях безопасности. Измените в docker-compose.yml при необходимости.',
        
        databaseSettings: 'Настройки базы данных',
        databaseSettingsDesc: 'Конфигурация подключения к базе данных (только чтение)',
        databaseUrl: 'URL базы данных',
        redisUrl: 'URL Redis',
        
        taskQueueSettings: 'Настройки очереди задач',
        taskQueueSettingsDesc: 'Конфигурация очереди задач Celery (только чтение)',
        brokerUrl: 'URL брокера',
        resultBackend: 'Backend результатов',
        
        storageSettings: 'Настройки хранилища',
        storageSettingsDesc: 'Конфигурация хранилища MinIO S3-совместимого (только чтение)',
        minioEndpoint: 'Адрес MinIO',
        bucketName: 'Название bucket',
        accessKey: 'Ключ доступа',
        secureConnection: 'Безопасное соединение (TLS)',
        
        sshSettings: 'Настройки SSH',
        sshSettingsDesc: 'Конфигурация поведения SSH соединений',
        hostKeyPolicy: 'Политика ключей хостов',
        autoAddDesc: 'auto_add = Автоматически принимать новые ключи хостов (TOFU - Доверие при первом использовании)',
        
        changeUsername: 'Изменить имя пользователя',
        changeUsernameDesc: 'Обновите имя пользователя для входа. После изменения потребуется повторный вход.',
        currentPasswordForVerification: 'Текущий пароль (для подтверждения)',
        newUsername: 'Новое имя пользователя',
        updateUsername: 'Обновить имя пользователя',
        
        changePassword: 'Изменить пароль',
        changePasswordDesc: 'Обновите пароль для безопасности учетной записи. Используйте надежный пароль из минимум 8 символов.',
        currentPassword: 'Текущий пароль',
        newPassword: 'Новый пароль',
        confirmPassword: 'Подтвердите новый пароль',
        updatePassword: 'Обновить пароль',
        
        noteTitle: 'Примечание:',
        noteText: 'После изменения имени пользователя или пароля вы будете автоматически разлогинены и должны войти снова с новыми учетными данными.',
        
        // Login Page
        welcomeBack: 'Добро пожаловать',
        loginPrompt: 'Пожалуйста, введите свои учетные данные',
        signIn: 'Войти',
        signingIn: 'Вход...',
        
        // Messages
        loading: 'Загрузка...',
        yes: 'Да',
        no: 'Нет',
        
        // Theme & Language
        themeLight: 'Переключить на светлую тему',
        themeDark: 'Переключить на темную тему',
    }
};

// Get translation
function t(key) {
    const lang = getCurrentLanguage();
    return translations[lang]?.[key] || translations['en'][key] || key;
}

// Apply translations to page
function applyTranslations() {
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        const translation = t(key);
        
        // Handle different element types
        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
            if (element.placeholder !== undefined) {
                element.placeholder = translation;
            }
        } else {
            element.textContent = translation;
        }
    });
    
    // Update language toggle button
    const langToggle = document.getElementById('langToggle');
    if (langToggle) {
        const currentLang = getCurrentLanguage();
        langToggle.textContent = currentLang === 'en' ? 'RU' : 'EN';
        langToggle.title = currentLang === 'en' ? 'Переключить на русский' : 'Switch to English';
    }
}

// Toggle language
function toggleLanguage() {
    const currentLang = getCurrentLanguage();
    const newLang = currentLang === 'en' ? 'ru' : 'en';
    localStorage.setItem(LANG_KEY, newLang);
    applyTranslations();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Apply saved theme
    applyTheme(getCurrentTheme());
    
    // Apply translations
    applyTranslations();
    
    // Setup theme toggle
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Setup language toggle
    const langToggle = document.getElementById('langToggle');
    if (langToggle) {
        langToggle.addEventListener('click', toggleLanguage);
    }
});
