/**
 * Testum - Theme and i18n utilities
 */

// ===== THEME MANAGEMENT =====
const THEME_KEY = 'testum-theme';
const LANG_KEY = 'testum-language';
const DEFAULT_THEME = 'dark';

function normalizeTheme(value) {
    return value === 'light' ? 'light' : DEFAULT_THEME;
}

// Initialize theme IMMEDIATELY to prevent flash
(function initializeTheme() {
    let savedTheme = DEFAULT_THEME;

    try {
        const stored = localStorage.getItem(THEME_KEY);
        if (stored) {
            savedTheme = normalizeTheme(stored);
        } else {
            const currentAttr = document.documentElement.getAttribute('data-theme');
            savedTheme = normalizeTheme(currentAttr);
        }
    } catch (error) {
        const currentAttr = document.documentElement.getAttribute('data-theme');
        savedTheme = normalizeTheme(currentAttr);
    }

    document.documentElement.setAttribute('data-theme', savedTheme);
    document.documentElement.style.colorScheme = savedTheme;

    if (document.body) {
        document.body.setAttribute('data-theme', savedTheme);
        document.body.style.colorScheme = savedTheme;
    }
})();

// Get current theme
function getCurrentTheme() {
    try {
        const saved = localStorage.getItem(THEME_KEY);
        return normalizeTheme(saved);
    } catch (error) {
        const currentAttr = document.documentElement.getAttribute('data-theme');
        return normalizeTheme(currentAttr);
    }
}

// Get current language
function getCurrentLanguage() {
    return localStorage.getItem(LANG_KEY) || 'en';
}

// Apply theme
function applyTheme(theme) {
    const resolvedTheme = normalizeTheme(theme);

    document.documentElement.setAttribute('data-theme', resolvedTheme);
    document.documentElement.style.colorScheme = resolvedTheme;

    if (document.body) {
        document.body.setAttribute('data-theme', resolvedTheme);
        document.body.style.colorScheme = resolvedTheme;
    }

    try {
        localStorage.setItem(THEME_KEY, resolvedTheme);
    } catch (error) {
        // Ignore storage errors (e.g., privacy mode)
    }

    // Update theme toggle button
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        const icon = resolvedTheme === 'dark' ? 'light_mode' : 'dark_mode';
        const iconElement = themeToggle.querySelector('.material-symbols-rounded');
        if (iconElement) {
            iconElement.textContent = icon;
        } else {
            themeToggle.innerHTML = `<span class="material-symbols-rounded" aria-hidden="true">${icon}</span>`;
        }
        themeToggle.title = resolvedTheme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme';
        themeToggle.setAttribute('aria-label', themeToggle.title);
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
        scripts: 'Scripts',
        automations: 'Automations',
        jobs: 'Jobs',
        virtualization: 'Virtualization',
        virtVms: 'Virtual Machines',
        virtPools: 'Storage Pools',
        virtVolumes: 'Volumes',

        // Virt pages — common
        platformLabel: 'Platform:',
        poolLabel: 'Pool:',
        close: 'Close',
        cancel: 'Cancel',
        delete: 'Delete',
        activate: 'Activate',
        deactivate: 'Deactivate',
        selectPlatformFirst: 'Select a platform to load data.',
        loading: 'Loading…',

        // Virtual Machines page
        virtVmsSubtitle: 'Manage virtual machines on libvirt platforms.',
        installLibvirtBtn: 'Install libvirt',
        vmName: 'Name', vmUuid: 'UUID', vmState: 'State', vmMemory: 'Memory', vmVcpus: 'vCPUs', vmAutostart: 'Autostart',
        vmSelectPlatform: 'Select a platform to load VMs.',
        vmNoVms: 'No VMs found on this platform.',
        startVm: 'Start', stopVm: 'Stop', deleteVm: 'Delete',
        deleteVmTitle: 'Delete VM',
        deleteVmBody: 'The VM will be force-stopped and undefined.',
        installModalTitle: 'Install libvirt & dependencies',
        installModalDesc: 'Connects to the selected platform via SSH, detects the OS, and installs <code>qemu-kvm</code>, <code>libvirt</code>, and related packages. The user is added to the <code>libvirt</code> group and the service is enabled. Progress is tracked as a Job and visible in the Audit Log.',
        installOutputPlaceholder: 'Press Run Install to start.',
        viewJob: 'View Job',
        liveMonitor: 'Live Monitor',
        runInstall: 'Run Install',

        // Storage Pools page
        virtPoolsSubtitle: 'Manage libvirt storage pools on your platforms.',
        addPool: 'Add Pool',
        poolColName: 'Name', poolColState: 'State', poolColVolumes: 'Volumes',
        poolColCapacity: 'Capacity', poolColUsage: 'Usage', poolColAutostart: 'Autostart',
        poolSelectPlatform: 'Select a platform to load pools.',
        poolNone: 'No storage pools found.',
        addPoolTitle: 'Add Storage Pool',
        poolNameLabel: 'Name *', poolTypeLabel: 'Type *',
        poolSourceLabel: 'Source (device / path / host)',
        poolTargetLabel: 'Target path',
        poolHostLabel: 'Host (for netfs / iSCSI)',
        createPool: 'Create Pool',
        deletePoolTitle: 'Delete Pool',
        deletePoolBody: 'This will undefine and delete the pool from the hypervisor.',

        // Volumes page
        virtVolumesSubtitle: 'Manage storage volumes inside libvirt pools.',
        addVolume: 'Add Volume',
        volColName: 'Name', volColType: 'Type', volColCapacity: 'Capacity (GB)', volColAlloc: 'Allocation (GB)',
        volSelectPlatform: 'Select a platform and pool to load volumes.',
        volSelectPool: 'Select a pool to load volumes.',
        volNone: 'No volumes in this pool.',
        addVolumeTitle: 'Add Volume',
        volNameLabel: 'Name *', volPathLabel: 'Full path *', volCapLabel: 'Capacity (GB) *',
        createVolume: 'Create Volume',
        deleteVolumeTitle: 'Delete Volume',
        deleteVolumeBody: 'Permanently delete this volume? This cannot be undone.',

        system: 'System',
        users: 'Users',
        auditLogs: 'Audit Logs',
        settings: 'Settings',
        healthCheck: 'Health Check',
        apiDocs: 'API Docs',
        
        // Dashboard
        welcomeTitle: 'Testum',
        welcomeSubtitle: 'Remote SSH Execution Platform',
        welcomeDescription: 'Execute commands and code on remote hosts via SSH',
        sshKeysCard: 'SSH Keys',
        sshKeysDescription: 'Manage public SSH keys for deployment',
        platformsCard: 'Platforms',
        platformsDescription: 'Configure target SSH hosts',
        tasksCard: 'Tasks',
        tasksDescription: 'Monitor running tasks',
        healthCheckCard: 'System Status',
        healthCheckDescription: 'Monitor system health and performance',
        currentStatus: 'Current status',
        statusLabel: 'Status:',
        timestampLabel: 'Last checked:',
        statsTitle: 'Statistics',
        totalKeys: 'SSH Keys',
        totalPlatforms: 'Platforms',
        activeTasks: 'Active Tasks',
        connectedPlatforms: 'Connected Platforms',
        viewAll: 'View All',
        noPlatforms: 'No platforms configured yet',
        addFirstPlatform: 'Add your first platform',
        
        // SSH Keys Page
        sshKeysTitle: 'SSH Keys',
        sshKeysSubtitle: 'Manage SSH public keys for deployment to platforms',
        addNewKey: 'Add New Key',
        keyName: 'Key Name',
        publicKey: 'Public Key',
        privateKeyOptional: 'Private Key (Optional, for platform authentication)',
        privateKeyNote: 'If provided, this key can be used to authenticate to platforms',
        addKey: 'Add Key',
        existingKeys: 'Existing Keys',
        noKeysFound: 'No SSH keys found. Add your first key above.',
        created: 'Created',
        delete: 'Delete',
        
        // Platforms Page
        platformsTitle: 'Platforms',
        platformsSubtitle: 'Compact overview of SSH targets and quick actions',
        addPlatform: 'Add Platform',
        platformName: 'Platform Name',
        host: 'Host',
        port: 'Port',
        username: 'Username',
        authMethod: 'Authentication Method',
        password: 'Password',
        privateKey: 'Private Key',
        sshKey: 'SSH Key',
        existingPlatforms: 'Existing Platforms',
        noPlatformsFound: 'No platforms found. Add your first platform above.',
        deployKeys: 'Deploy Keys',
        runCommand: 'Run Command',
        platformOs: 'OS',
        platformKernel: 'Kernel',
        platformCpu: 'CPU',
        platformMemory: 'Memory',
        platformUptime: 'Uptime',
        notAvailable: 'Not available',
        platformAuthPassword: 'Password',
        platformAuthKey: 'SSH Key',

        // Scripts Page
        scriptsTitle: 'Scripts',
        scriptsSubtitle: 'Store and reuse automation snippets for deployments',
        scriptsLibrary: 'Script Library',
        newScript: 'New Script',
        noScriptsFound: 'No scripts saved yet.',
        noDescription: 'No description provided.',
        scriptName: 'Script name',
        scriptLanguage: 'Language',
        scriptDescription: 'Description',
        scriptContent: 'Script content',
        saveScript: 'Save Script',
        updateScript: 'Update Script',
        deleteScript: 'Delete Script',
        resetForm: 'Reset',
        createScriptTitle: 'Create script',
        editScriptTitle: 'Edit script',
        createdLabel: 'Created',
        updatedLabel: 'Updated',
        confirmDeleteScript: 'Delete this script?',
        loadError: 'Failed to load scripts.',
        saveError: 'Unable to save script.',
        deleteError: 'Unable to delete script.',

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
    taskQueueSettingsDesc: 'Task queue configuration (read-only)',
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
        
        // Common UI states
        loading: 'Loading...',
        yes: 'Yes',
        no: 'No',
        save: 'Save',
        cancel: 'Cancel',
        delete: 'Delete',
        edit: 'Edit',
        refresh: 'Refresh',
        details: 'Details',
        noTasksFound: 'No tasks found',
        noUsersFound: 'No users found',
        noAuditFound: 'No audit logs found',
        loadingTasks: 'Loading tasks…',
        loadingUsers: 'Loading users…',
        loadingAudit: 'Loading…',
        failedToLoad: 'Failed to load',
        errorPrefix: 'Error: ',
        noScriptsAvailable: 'No scripts',
        noAutomationsFound: 'No automations yet. Add one and Testum will remember the schedule.',
        failedToLoadAutomations: 'Failed to load automations',
        addNewPlatform: 'Add New Platform',
        editPlatform: 'Edit Platform',
        addNewKey: 'Add New SSH Key',
        editKey: 'Edit SSH Key',
        addUser: 'Add User',
        editUser: 'Edit User',
        enabled: 'Enabled',
        disabled: 'Disabled',
        notSet: 'Not Set',
        usernameUpdated: 'Username updated successfully',
        passwordUpdated: 'Password updated successfully',
        backupStarted: 'Backup export started…',
        backupImported: 'Backup imported successfully',
        gitopsSuccess: 'GitOps import successful',
        dryRunDone: 'Dry run completed — no changes made',
        platformDeleted: 'Platform deleted successfully',
        keyDeleted: 'Key deleted successfully',
        keyAdded: 'Key added successfully',
        userDeleted: 'User deleted successfully',
        userUpdated: 'User updated',
        userCreated: 'User created',
        passwordsMismatch: 'Passwords do not match',
        passwordTooShort: 'Password must be at least 6 characters',
        gitUrlRequired: 'Git URL is required',
        cloningRepo: 'Cloning Git repository…',
        connectionError: 'Connection error. Please try again.',
        refresh: 'Refresh',
        usersSubtitle: 'Invite teammates, assign roles, and control access to Testum.',
        jobsSubtitle: 'Track execution history and live status for your automation jobs.',

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
        scripts: 'Скрипты',
        automations: 'Автоматизация',
        jobs: 'Задачи',
        virtualization: 'Виртуализация',
        virtVms: 'Виртуальные машины',
        virtPools: 'Пулы хранилищ',
        virtVolumes: 'Тома',

        // Virt pages — common
        platformLabel: 'Платформа:',
        poolLabel: 'Пул:',
        close: 'Закрыть',
        cancel: 'Отмена',
        delete: 'Удалить',
        activate: 'Активировать',
        deactivate: 'Деактивировать',
        selectPlatformFirst: 'Выберите платформу для загрузки данных.',
        loading: 'Загрузка…',

        // Virtual Machines page
        virtVmsSubtitle: 'Управление виртуальными машинами на платформах libvirt.',
        installLibvirtBtn: 'Установить libvirt',
        vmName: 'Имя', vmUuid: 'UUID', vmState: 'Состояние', vmMemory: 'Память', vmVcpus: 'vCPU', vmAutostart: 'Автозапуск',
        vmSelectPlatform: 'Выберите платформу для загрузки ВМ.',
        vmNoVms: 'Виртуальные машины не найдены.',
        startVm: 'Запустить', stopVm: 'Остановить', deleteVm: 'Удалить',
        deleteVmTitle: 'Удалить ВМ',
        deleteVmBody: 'ВМ будет принудительно остановлена и удалена из конфигурации.',
        installModalTitle: 'Установка libvirt и зависимостей',
        installModalDesc: 'Подключается к выбранной платформе по SSH, определяет ОС и устанавливает <code>qemu-kvm</code>, <code>libvirt</code> и сопутствующие пакеты. Пользователь добавляется в группу <code>libvirt</code>, сервис включается. Прогресс отображается в разделе Задачи и Журнале событий.',
        installOutputPlaceholder: 'Нажмите «Запустить установку», чтобы начать.',
        viewJob: 'Открыть задачу',
        liveMonitor: 'Монитор',
        runInstall: 'Запустить установку',

        // Storage Pools page
        virtPoolsSubtitle: 'Управление пулами хранилищ libvirt на ваших платформах.',
        addPool: 'Добавить пул',
        poolColName: 'Имя', poolColState: 'Состояние', poolColVolumes: 'Тома',
        poolColCapacity: 'Объём', poolColUsage: 'Использование', poolColAutostart: 'Автозапуск',
        poolSelectPlatform: 'Выберите платформу для загрузки пулов.',
        poolNone: 'Пулы хранилищ не найдены.',
        addPoolTitle: 'Добавить пул хранилища',
        poolNameLabel: 'Имя *', poolTypeLabel: 'Тип *',
        poolSourceLabel: 'Источник (устройство / путь / хост)',
        poolTargetLabel: 'Путь назначения',
        poolHostLabel: 'Хост (для netfs / iSCSI)',
        createPool: 'Создать пул',
        deletePoolTitle: 'Удалить пул',
        deletePoolBody: 'Пул будет удалён из конфигурации гипервизора.',

        // Volumes page
        virtVolumesSubtitle: 'Управление томами внутри пулов libvirt.',
        addVolume: 'Добавить том',
        volColName: 'Имя', volColType: 'Тип', volColCapacity: 'Объём (ГБ)', volColAlloc: 'Выделено (ГБ)',
        volSelectPlatform: 'Выберите платформу и пул для загрузки томов.',
        volSelectPool: 'Выберите пул для загрузки томов.',
        volNone: 'В этом пуле нет томов.',
        addVolumeTitle: 'Добавить том',
        volNameLabel: 'Имя *', volPathLabel: 'Полный путь *', volCapLabel: 'Объём (ГБ) *',
        createVolume: 'Создать том',
        deleteVolumeTitle: 'Удалить том',
        deleteVolumeBody: 'Удалить том безвозвратно? Это действие нельзя отменить.',

        system: 'Система',
        users: 'Пользователи',
        auditLogs: 'Журнал событий',
        settings: 'Настройки',
        healthCheck: 'Проверка здоровья',
        apiDocs: 'API Документация',
        
        // Dashboard
        welcomeTitle: 'Testum',
        welcomeSubtitle: 'Платформа удаленного выполнения через SSH',
        welcomeDescription: 'Выполняйте команды и код на удаленных хостах через SSH',
        sshKeysCard: 'SSH Ключи',
        sshKeysDescription: 'Управление публичными SSH ключами для развертывания',
        platformsCard: 'Платформы',
        platformsDescription: 'Настройка целевых SSH хостов',
        tasksCard: 'Задачи',
        tasksDescription: 'Мониторинг выполняемых задач',
        healthCheckCard: 'Статус системы',
        healthCheckDescription: 'Мониторинг состояния и производительности системы',
        currentStatus: 'Текущий статус',
        statusLabel: 'Статус:',
        timestampLabel: 'Время проверки:',
        statsTitle: 'Статистика',
        totalKeys: 'SSH Ключи',
        totalPlatforms: 'Платформы',
        activeTasks: 'Активные задачи',
        connectedPlatforms: 'Подключенные платформы',
        viewAll: 'Показать все',
        noPlatforms: 'Платформы ещё не настроены',
        addFirstPlatform: 'Добавить первую платформу',
        
        // SSH Keys Page
        sshKeysTitle: 'SSH Ключи',
        sshKeysSubtitle: 'Управление публичными SSH ключами для развертывания на платформах',
        addNewKey: 'Добавить новый ключ',
        keyName: 'Название ключа',
        publicKey: 'Публичный ключ',
        privateKeyOptional: 'Приватный ключ (Опционально, для аутентификации на платформах)',
        privateKeyNote: 'Если указан, этот ключ можно использовать для подключения к платформам',
        addKey: 'Добавить ключ',
        existingKeys: 'Существующие ключи',
        noKeysFound: 'SSH ключи не найдены. Добавьте первый ключ выше.',
        created: 'Создан',
        delete: 'Удалить',
        
        // Platforms Page
        platformsTitle: 'Платформы',
        platformsSubtitle: 'Компактный обзор SSH-платформ и быстрых действий',
        addPlatform: 'Добавить платформу',
        platformName: 'Название платформы',
        host: 'Хост',
        port: 'Порт',
        username: 'Имя пользователя',
        authMethod: 'Метод аутентификации',
        password: 'Пароль',
        privateKey: 'Приватный ключ',
        sshKey: 'SSH ключ',
        existingPlatforms: 'Существующие платформы',
        noPlatformsFound: 'Платформы не найдены. Добавьте первую платформу выше.',
        deployKeys: 'Развернуть ключи',
        runCommand: 'Выполнить команду',
        platformOs: 'ОС',
        platformKernel: 'Ядро',
        platformCpu: 'Процессор',
        platformMemory: 'Память',
        platformUptime: 'Время работы',
        notAvailable: 'Нет данных',
        platformAuthPassword: 'Пароль',
        platformAuthKey: 'SSH-ключ',

        // Scripts Page
        scriptsTitle: 'Скрипты',
        scriptsSubtitle: 'Храните и переиспользуйте сценарии автоматизации для задач',
        scriptsLibrary: 'Библиотека скриптов',
        newScript: 'Новый скрипт',
        noScriptsFound: 'Скриптов пока нет.',
        noDescription: 'Описание не задано.',
        scriptName: 'Название скрипта',
        scriptLanguage: 'Язык',
        scriptDescription: 'Описание',
        scriptContent: 'Содержимое скрипта',
        saveScript: 'Сохранить скрипт',
        updateScript: 'Обновить скрипт',
        deleteScript: 'Удалить скрипт',
        resetForm: 'Сбросить',
        createScriptTitle: 'Создание скрипта',
        editScriptTitle: 'Редактирование скрипта',
        createdLabel: 'Создан',
        updatedLabel: 'Обновлен',
        confirmDeleteScript: 'Удалить этот скрипт?',
        loadError: 'Не удалось загрузить скрипты.',
        saveError: 'Не удалось сохранить скрипт.',
        deleteError: 'Не удалось удалить скрипт.',

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
    taskQueueSettingsDesc: 'Конфигурация очереди задач (только чтение)',
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
        save: 'Сохранить',
        cancel: 'Отмена',
        delete: 'Удалить',
        edit: 'Редактировать',
        refresh: 'Обновить',
        details: 'Детали',
        noTasksFound: 'Задачи не найдены',
        noUsersFound: 'Пользователи не найдены',
        noAuditFound: 'Журнал пуст',
        loadingTasks: 'Загрузка задач…',
        loadingUsers: 'Загрузка пользователей…',
        loadingAudit: 'Загрузка…',
        failedToLoad: 'Не удалось загрузить',
        errorPrefix: 'Ошибка: ',
        noScriptsAvailable: 'Скриптов нет',
        noAutomationsFound: 'Задачи пока не созданы. Добавьте первую — и Testum запомнит расписание.',
        failedToLoadAutomations: 'Не удалось загрузить задачи',
        addNewPlatform: 'Новая платформа',
        editPlatform: 'Редактировать платформу',
        addNewKey: 'Новый SSH-ключ',
        editKey: 'Редактировать ключ',
        addUser: 'Добавить пользователя',
        editUser: 'Редактировать пользователя',
        enabled: 'Включено',
        disabled: 'Отключено',
        notSet: 'Не задано',
        usernameUpdated: 'Имя пользователя обновлено',
        passwordUpdated: 'Пароль обновлён',
        backupStarted: 'Экспорт бэкапа запущен…',
        backupImported: 'Бэкап успешно импортирован',
        gitopsSuccess: 'GitOps импорт выполнен',
        dryRunDone: 'Пробный запуск завершён — изменений нет',
        platformDeleted: 'Платформа удалена',
        keyDeleted: 'Ключ удалён',
        keyAdded: 'Ключ добавлен',
        userDeleted: 'Пользователь удалён',
        userUpdated: 'Пользователь обновлён',
        userCreated: 'Пользователь создан',
        passwordsMismatch: 'Пароли не совпадают',
        passwordTooShort: 'Пароль должен содержать не менее 6 символов',
        gitUrlRequired: 'Необходимо указать URL репозитория',
        cloningRepo: 'Клонирование репозитория…',
        connectionError: 'Ошибка соединения. Попробуйте ещё раз.',
        refresh: 'Обновить',
        usersSubtitle: 'Управление командой, ролями и доступом к Testum.',
        jobsSubtitle: 'История выполнения и статус задач автоматизации.',

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

    // data-i18n-html: like data-i18n but sets innerHTML (for keys containing markup)
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
        el.innerHTML = t(el.getAttribute('data-i18n-html'));
    });
    
    // Update language toggle button
    const langToggle = document.getElementById('langToggle');
    if (langToggle) {
        const currentLang = getCurrentLanguage();
        const displayLang = currentLang === 'en' ? 'RU' : 'EN';
        langToggle.innerHTML = `<span aria-hidden="true">${displayLang}</span>`;
        const title = currentLang === 'en' ? 'Переключить на русский' : 'Switch to English';
        langToggle.title = title;
        langToggle.setAttribute('aria-label', title);
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
