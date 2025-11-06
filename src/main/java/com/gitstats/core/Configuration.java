package com.gitstats.core;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Properties;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Configuration management for GitStats application
 * Handles application settings, user preferences, and analysis options.
 */
public class Configuration {
    
    private static final Logger logger = LoggerFactory.getLogger(Configuration.class);
    private static Configuration instance;
    
    // Default configuration values
    private static final int DEFAULT_MAX_AUTHORS = 20;
    private static final int DEFAULT_TOP_AUTHORS = 5;
    private static final int DEFAULT_MAX_DOMAINS = 10;
    private static final int DEFAULT_MAX_EXT_LENGTH = 10;
    private static final int DEFAULT_PROCESSES = Math.min(4, Runtime.getRuntime().availableProcessors());
    
    // Configuration properties
    private final Properties properties;
    private final Set<String> allowedExtensions;
    
    private Configuration() {
        this.properties = new Properties();
        this.allowedExtensions = new HashSet<>();
        loadDefaults();
    }
    
    /**
     * Get singleton instance
     */
    public static synchronized Configuration getInstance() {
        if (instance == null) {
            instance = new Configuration();
        }
        return instance;
    }
    
    /**
     * Load default configuration values
     */
    private void loadDefaults() {
        // General settings
        properties.setProperty("max_authors", String.valueOf(DEFAULT_MAX_AUTHORS));
        properties.setProperty("top_authors", String.valueOf(DEFAULT_TOP_AUTHORS));
        properties.setProperty("max_domains", String.valueOf(DEFAULT_MAX_DOMAINS));
        properties.setProperty("max_ext_length", String.valueOf(DEFAULT_MAX_EXT_LENGTH));
        properties.setProperty("processes", String.valueOf(DEFAULT_PROCESSES));
        properties.setProperty("scan_default_branch_only", "true");
        properties.setProperty("filter_by_extensions", "true");
        properties.setProperty("calculate_mi_per_repository", "true");
        properties.setProperty("verbose", "false");
        properties.setProperty("debug", "false");
        
        // Multi-repo settings
        properties.setProperty("multi_repo_max_depth", "10");
        properties.setProperty("multi_repo_parallel", "false");
        properties.setProperty("multi_repo_max_workers", "2");
        properties.setProperty("multi_repo_timeout", "3600");
        properties.setProperty("multi_repo_batch_size", "10");
        
        // Load default allowed file extensions
        loadDefaultExtensions();
        
        logger.info("Default configuration loaded");
    }
    
    /**
     * Load default allowed file extensions
     */
    private void loadDefaultExtensions() {
        allowedExtensions.addAll(Arrays.asList(
            // C/C++
            ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
            // Objective-C
            ".m", ".mm",
            // Swift
            ".swift",
            // CUDA
            ".cu", ".cuh", ".cl",
            // Java
            ".java", ".scala", ".kt",
            // Go
            ".go",
            // Rust
            ".rs",
            // Python
            ".py", ".pyi", ".pyx", ".pxd",
            // JavaScript/TypeScript
            ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".d.ts",
            // Lua
            ".lua",
            // Protocol Buffers
            ".proto", ".thrift",
            // Assembly
            ".asm", ".s", ".S",
            // R
            ".R", ".r"
        ));
    }
    
    // Getters
    public int getMaxAuthors() {
        return Integer.parseInt(properties.getProperty("max_authors"));
    }
    
    public int getTopAuthors() {
        return Integer.parseInt(properties.getProperty("top_authors"));
    }
    
    public int getMaxDomains() {
        return Integer.parseInt(properties.getProperty("max_domains"));
    }
    
    public int getProcesses() {
        return Integer.parseInt(properties.getProperty("processes"));
    }
    
    public boolean isScanDefaultBranchOnly() {
        return Boolean.parseBoolean(properties.getProperty("scan_default_branch_only"));
    }
    
    public boolean isFilterByExtensions() {
        return Boolean.parseBoolean(properties.getProperty("filter_by_extensions"));
    }
    
    public boolean isVerbose() {
        return Boolean.parseBoolean(properties.getProperty("verbose"));
    }
    
    public boolean isDebug() {
        return Boolean.parseBoolean(properties.getProperty("debug"));
    }
    
    public Set<String> getAllowedExtensions() {
        return Collections.unmodifiableSet(allowedExtensions);
    }
    
    // Setters
    public void setMaxAuthors(int maxAuthors) {
        properties.setProperty("max_authors", String.valueOf(maxAuthors));
    }
    
    public void setTopAuthors(int topAuthors) {
        properties.setProperty("top_authors", String.valueOf(topAuthors));
    }
    
    public void setProcesses(int processes) {
        properties.setProperty("processes", String.valueOf(processes));
    }
    
    public void setScanDefaultBranchOnly(boolean scanDefaultOnly) {
        properties.setProperty("scan_default_branch_only", String.valueOf(scanDefaultOnly));
    }
    
    public void setFilterByExtensions(boolean filter) {
        properties.setProperty("filter_by_extensions", String.valueOf(filter));
    }
    
    public void setVerbose(boolean verbose) {
        properties.setProperty("verbose", String.valueOf(verbose));
    }
    
    public void setDebug(boolean debug) {
        properties.setProperty("debug", String.valueOf(debug));
    }
    
    /**
     * Check if a file should be included based on extension
     */
    public boolean shouldIncludeFile(String filename) {
        if (!isFilterByExtensions()) {
            return true;
        }
        
        // Handle hidden files
        String basename = new File(filename).getName();
        if (basename.startsWith(".") && !basename.equals(".")) {
            return false;
        }
        
        // Check if file has extension
        if (!filename.contains(".")) {
            // No extension - include common extensionless files
            Set<String> extensionlessIncludes = new HashSet<>(Arrays.asList(
                "Makefile", "Dockerfile", "Rakefile", "Gemfile", "CMakeLists"
            ));
            return extensionlessIncludes.contains(basename);
        }
        
        // Check extension
        String lowerFilename = filename.toLowerCase();
        return allowedExtensions.stream().anyMatch(lowerFilename::endsWith);
    }
    
    /**
     * Save configuration to file
     */
    public void save(File file) throws IOException {
        try (FileOutputStream fos = new FileOutputStream(file)) {
            properties.store(fos, "GitStats Configuration");
            logger.info("Configuration saved to: {}", file.getAbsolutePath());
        }
    }
    
    /**
     * Load configuration from file
     */
    public void load(File file) throws IOException {
        try (FileInputStream fis = new FileInputStream(file)) {
            properties.load(fis);
            logger.info("Configuration loaded from: {}", file.getAbsolutePath());
        }
    }
    
    /**
     * Get property value
     */
    public String getProperty(String key) {
        return properties.getProperty(key);
    }
    
    /**
     * Set property value
     */
    public void setProperty(String key, String value) {
        properties.setProperty(key, value);
    }
    
    /**
     * Get all properties
     */
    public Properties getProperties() {
        return new Properties(properties);
    }
}
