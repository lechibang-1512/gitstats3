package com.gitstats;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Launcher class for GitStats JavaFX Application
 * 
 * This class serves as a workaround for running JavaFX applications
 * from a JAR file without module-path issues. It does not extend
 * javafx.application.Application, which prevents module errors when
 * JavaFX is included as a regular dependency.
 * 
 * Usage:
 *   java -jar gitstats-3.0.0.jar
 * 
 * The launcher will invoke GitStatsApplication.main() which then
 * calls Application.launch().
 */
public class Launcher {
    
    private static final Logger logger = LoggerFactory.getLogger(Launcher.class);
    
    /**
     * Main entry point for JAR execution
     * 
     * This method simply delegates to GitStatsApplication.main()
     * to start the JavaFX application.
     */
    public static void main(String[] args) {
        logger.info("Launcher.main() called - Starting GitStats Application");
        
        try {
            // Delegate to the actual JavaFX Application class
            GitStatsApplication.main(args);
        } catch (Exception e) {
            logger.error("Failed to launch GitStats Application", e);
            System.err.println("Error launching GitStats: " + e.getMessage());
            System.exit(1);
        }
    }
}
